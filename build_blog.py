#!/usr/bin/env python3

import sqlite3
from os import makedirs, path

pybb = "pybb.db"
outdir = "blog"
index_len = 10

header = """
<html>
<head><title>This is a blog</title></head>
<body>"""

footer = """
</body></html>"""

conn = sqlite3.connect(pybb)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print(header)
print("<ul>")
for row in cur.execute("SELECT title, publish_date, filename FROM posts "
                       "ORDER BY publish_date DESC LIMIT ?",
                       (index_len,)):
    pd = row["publish_date"]
    datedir = path.join(pd[0:4], pd[5:7])
    makedirs(path.join(outdir, datedir), mode=0o750, exist_ok=True)
    outfile = path.join(outdir, datedir, row["filename"])
    with open(outfile, 'w', encoding="utf-8") as f:
        f.write("Placeholder.")
    print(("<li><strong>{publish_date}</strong>"
          "<a href=\"{outfile}\">{title}</a></li>")
          .format(outfile=outfile, publish_date=pd, title=row["title"]))
print("</ul>")
print(footer)
conn.close()