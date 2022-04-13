from dataclasses import field, dataclass
from collections import defaultdict
from itertools import groupby
from datetime import datetime
import imaplib
import email
from bs4 import BeautifulSoup
from sanitize_filename import sanitize

# Class with options to alter the behaviour
@dataclass
class Config:
    include_metadata: bool = True     # If true, include a first block with metadata
    append_file: bool = False         # If true, append instead of overwriting
    include_date_in_notes: bool = False  # If true, each note includes the date in which it was taken
    include_chapter_in_notes: bool = False   # If true, each note includes the chapter to which it belongs
    group_by: str = "all"             # Possible values: "date", "chapter", "all".
    color_map: dict = field(default_factory=dict)  # Maps between colors and icons
    join_titles: bool = True          # If a color is replaced by a heading mark, join with spaces all lines in that highlight
    dump_stdout: bool = False         # Dump to stdout instead of file
    html_parser: str = "html.parser"  # It can be lxml if the library is installed

# Class with email configuration parameters
@dataclass
class EmailConfig:
    login: str
    server: str
    passwd: str
    subject: str  # This has to be set to the string which Apple Books sends in the subject of the email

# Class to store each annotation
@dataclass
class Annotation:
    date: str
    chapter: str
    color: str
    text: str
    note: str

# Class to store the metadata
@dataclass
class MetaData:
    title: str = "Untitled"
    author: str = "Unkown"
    source: str = "Unspecified"
    imported: datetime = field(default_factory=lambda: datetime.now())


# Main class which does all the job
class AnnotationExtractor:
    def __init__(self, email_cfg: EmailConfig, cfg: Config):
        self.email_cfg = email_cfg
        self.cfg = cfg
        self.mail_connection = None

    @staticmethod
    def _extract_annotation(e) -> Annotation:
        """Extracts relevant info from html element for a single annotation"""
        date = e.find(class_="annotationdate").text.strip()
        chapter = e.find(class_="annotationchapter").text.strip()
        color = e.find(class_="annotationselectionMarker").attrs["class"][-1]
        text = e.find(class_="annotationrepresentativetext").text.strip()
        note = e.find(class_="annotationnote").text.strip()
        return Annotation(date, chapter, color, text, note)

    def _format_annotation(self, a, indent=""):
        """Receives a single annotation and returns a formatted string,
        ready to be dumped in the markdown file"""
        prefix = self.cfg.color_map.get(a.color, "")
        if prefix in ("#", "##", "###", "####") and self.cfg.join_titles:
            a.text = " ".join(a.text.split())
        if prefix:
            prefix += " "
        fmtd = f"{indent}- {prefix}{a.text}"
        if self.cfg.include_chapter_in_notes:
            fmtd += f" (Chapter '{a.chapter}')"
        if self.cfg.include_date_in_notes:
            fmtd += f"({a.date})"
        if a.note:
            note_icon = self.cfg.color_map.get("note", "")
            if note_icon:
                note_icon+=" "
            fmtd += f"\n{indent}    - {note_icon}{a.note}"
        return fmtd

    def _extract_annotations_from_html(self, html):
        """Receives the HTML wihch is attached in the email and scrapes
        it to extract all anotations and metainfo.

        Returns a tuple with two objects: Metadata and a list of Annotation objects
        """
        def extract_if_not_none(elem) -> str:
            if elem:
                return elem.text.strip()
            else:
                return "Not specified"

        soup = BeautifulSoup(html, features=self.cfg.html_parser)
        result = []
        # Extract annotations
        for _, e in enumerate(soup.find_all(class_="annotation")):
            result.append(self._extract_annotation(e))

        # Extract book title and author
        title = extract_if_not_none(soup.h1)
        author = extract_if_not_none(soup.h2)
        ref = extract_if_not_none(soup.find(class_="citation"))
        if ref!="Not specified":
            ref = ref.split("\n")[0].strip()
        return MetaData(title=title, author=author, source=ref), result

    def group_and_dump(self, group_keys, annotations, indent):
        """Groups the list of annotatios for the first
        field in the list group_keys, and dumps a header for the group
        followed by the the result of calling recursively itself
        (to group for the next field in group_keys)

        If there is no field to group on, or if the field is invalid,
        the list of annotations is dumped, stopping the recursive calls

        It returns the list of lines produced
        """
        lines = []
        if not group_keys or not hasattr(annotations[0], group_keys[0]):
            group_key = None
        else:
            group_key = group_keys[0]
        groups = {}
        if group_key is None:
            return [self._format_annotation(annotation, indent=indent) for annotation in annotations]

        # Grouping has to be performed, so we first sort and group by that key
        key = lambda e: getattr(e, group_key)
        for k, g in groupby(sorted(annotations, key=key), key=key):
            groups[k] = list(g)
        # And then dump the result (recursively)
        for group, annotations in groups.items():
            level = len(indent)//4
            header = "#"*(level+1)
            lines.append(f"{indent}- {header} {group}")
            lines.extend(self.group_and_dump(group_keys[1:], annotations, indent+"    "))
        return lines

    def generate_markdown(self, metadata, annotations):
        # Prepare markdown contents
        if not annotations:
            return
        lines = []
        if self.cfg.include_metadata:
            lines.append(f'- title:: "{metadata.title}"')
            lines.append(f'  author:: "{metadata.author}"')
            lines.append(f'  source:: "{metadata.source}"')
            lines.append(f"  imported:: {metadata.imported}")

        group_keys = self.cfg.group_by
        if type(group_keys) == str:    # Allow a single group key, without a list
            group_keys = [group_keys]
        lines.extend(self.group_and_dump(group_keys, annotations, indent=""))
        return "\n".join(lines)

    def extract_html_from_email(self, id_:str) -> str:
        """ This function retrieves a single email and extracts the html part"""
        if self.mail_connection is None:
            return ""
        _, data = self.mail_connection.fetch(id_,'(RFC822)')
        html = ""
        for response_part in data :
            if not isinstance(response_part,tuple):
                continue
            msg = email.message_from_bytes(response_part[1])
            for _, part in enumerate(msg.walk()):
                if part.get_content_subtype() == 'html':
                    html = part.get_payload(decode=True)
                    break
            return html

    def _imap_connect(self):
        self.mail_connection = imaplib.IMAP4_SSL(self.email_cfg.server)
        self.mail_connection.login(self.email_cfg.login, self.email_cfg.passwd)
        self.mail_connection.select('inbox')

    def process_emails(self):
        """This function connects to the mail server, searches all emails
        with the appropiate subject, and writes a markdown file for
        each one (after extracting the annotations)"""

        self._imap_connect()
        if "gmail" in self.email_cfg.server:
            _, data = self.mail_connection.search(None, 'X-GM-RAW', f'"{e_cfg.subject}"')
        else:
            _, data = self.mail_connection.uid('search', "", f'(SUBJECT "{e_cfg.subject}")')

        mail_ids=data[0].decode()
        id_list=mail_ids.split()
        if not id_list:
            print(f"You don't have any email in your inbox whose subject contains {self.email_cfg.subject!r}")
            print("You may need to change that string in the configuration file")
            return
        for id_ in id_list:
            html = self.extract_html_from_email(id_)
            metadata, annotations = self._extract_annotations_from_html(html)
            md = self.generate_markdown(metadata, annotations)
            fname = f"{metadata.title}-{metadata.author}-Notes.md"
            self.dump_markdown(md, fname)

    def dump_markdown(self, md, fname):
        if self.cfg.dump_stdout:
            print(md)
            return
        if self.cfg.append_file:
            mode = "a"
        else:
            mode = "w"
        fname = sanitize(fname)
        with open(fname, mode) as f:
            if self.cfg.append_file: f.write("\n")
            f.write(md)
        print(f"Annotations written in {fname}")


import json
def read_pseudo_json(filename):
    # The configuration is stored in a json file with comments
    # This is not standard json, so we have to filter-out the
    # comments
    def is_comment(line):
        return line.lstrip().startswith("#")

    try:
        with open(filename) as f:
            data = "\n".join(line for line in f if not is_comment(line))
            config = json.loads(data)
    except OSError:
        print("You must have a file named .get_annotations.cfg")
        quit()
    except json.JSONDecodeError as e:
        print("The json in .get_annotations.cfg is not valid")
        print(e)
        quit()
    return config

# The main program creates the appropriate config objects (from the configuration
# file named .get_annotations.cfg) and calls process_emails
if __name__ == "__main__":
    from pathlib import Path
    config_file = Path(__file__).parent / Path("gabhil.cfg")
    config = read_pseudo_json(config_file)
    e_cfg= EmailConfig(**config.get("email"))
    cfg = Config(**config.get("options"))
    extractor = AnnotationExtractor(e_cfg, cfg)
    extractor.process_emails()