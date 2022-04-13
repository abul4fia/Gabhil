# Gabhil
Get Apple Books Highlights Into Logseq

## Purpose
Apple Book is a nice platform for reading, which allows highlighting (in different colors) and taking notes while reading. However it is not easy to extract the highlights and annotations from the app. The only way is to email these annotations to himself.

Gabhil is a script which connects with your email account, fetches the emails created by Apple Books, parses the contents, and generates a Markdown file ready to be imported into Logseq (in fact, the markdown generated is pretty standard, so it can be probably used with any markdown-based note taking application, but I had Logseq in mind when designing it, and it is the only one tested).

## Installation

You'll need a recent Python version (it was developed and tested using Python 3.10, but probably 3.7 will be ok too).

Clone this repository. Do a `pip install -r requirements.txt`, preferably in a virtual environment (this basically installs BeautifulSoup4, so perhaps you don't need to perform this step if you already have this library).

Edit `gabhil.cfg` to include your email credentials, and customize the options to your taste. The file is commented.

That's all.

**Note**. If you use gmail, you'll have to set up an "application password" and use it in the configuration file, instead of your "main password". Using your main password is insecure, and Google will forbid it. In order to generate an application password you need to activate double-factor authentication in Google (https://myaccount.google.com/security)

**Note2**. The script was tested only with gmail. In principle it should work with other email providers, but I cannot guarantee it, since it was not tested.

## Procedure

Open any book in Apple Books. Read it and take notes. Once you have a good number of highlights, do the following:

* Tap in the "table of contents icon (top left)
* Select the "Notes" tab (the third one)
* Tap in the "Share" icon (top left), and select "Edit Notes"
* Select all notes and "Share"
* Select Mail and put yourself as recipient

You can open your mail client to ensure that the email has reached your inbox. After this you simpy run:

```
python gabhil.py
```

Provided that the `gabhil.cfg` is properly configured, you'll see in your terminal some messages telling you which files were written. Each message in your inbox containing Apple Book highlights will produce a separate file. If several mails contain notes for the same book, the same file will be overwritten, but since the emails are processed from oldest to newest, the file will contain the latest version of the notes.


Open one of these files and look how your highlights and notes were converted to markdown. Modify `gabhil.cfg` until you are happy with the results. Then, you can copy this markdown file into your `pages/` folder in logseq.

It is advisable to remove the processed messages from the inbox in your mail, so that they are not processed again in the next run of gabhil.

Happy reading!
