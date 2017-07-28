#!/usr/bin/env python3

import sqlite3
import locale
from os import makedirs, path
from markdown import markdown
from datetime import datetime

pybb = "pybb.db"
outdir = "blog"
index_len = 10

locale.setlocale(locale.LC_ALL, 'fi_FI.utf8')

header = \
"""<!doctype html>
<html>
<head>
    <meta charset="utf-8" />
    <title>This is a blog</title>
</head>
<body>
"""

footer = """
</body></html>"""

dateformat = "%-d. %Bta %Y"
def pubdate2str(pubdate, formatstr):
    pd = datetime.strptime(pubdate, "%Y-%m-%d %H:%M:%S")
    return pd.strftime(formatstr)

conn = sqlite3.connect(pybb)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Make blog index
def makeindex():
    makedirs(outdir, exist_ok=True)
    idxf = open(outdir + "/index.html", 'w+', encoding="utf-8")
    
    idxf.write(header)
    idxf.write("<ul>\n")
    for row in cur.execute("SELECT title, publish_date, filename "
                           "FROM posts ORDER BY publish_date DESC LIMIT ?",
                           (index_len,)):
        pdstring = pubdate2str(row["publish_date"], dateformat)
        datedir = path.join(row["publish_date"][0:4], row["publish_date"][5:7])
        outfile = path.join(datedir, row["filename"]) + ".html"
        idxf.write(("    <li><strong>{publish_date}</strong> "
                    "<a href=\"{outfile}\">{title}</a></li>\n")
                    .format(outfile=outfile, publish_date=pdstring, title=row["title"]))
    idxf.write("</ul>\n")
    idxf.write(footer)
    
    idxf.seek(0)
    print(idxf.read())
    idxf.close()

# Write posts to files
def writeposts():
    for row in cur.execute("SELECT title, publish_date, filename, content "
                       "FROM posts"):
    pdstring = pubdate2str(row["publish_date"], dateformat)
    datedir = path.join(row["publish_date"][0:4], row["publish_date"][5:7])
    makedirs(path.join(outdir, datedir), mode=0o750, exist_ok=True)
    outfile = path.join(outdir, datedir, row["filename"]) + ".html"
    # Write each post file
    with open(outfile, 'w', encoding="utf-8") as f:
        f.write(header)
        f.write("<h1>" + row["title"] + "</h1>\n" + "<p>" + pdstring + "</p>\n")
        f.write(markdown(row["content"]))
        f.write(footer)


# Invoke functions from here

writeposts()
makeindex()

conn.close()