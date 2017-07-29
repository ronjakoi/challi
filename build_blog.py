#!/usr/bin/env python3

import sqlite3
import locale
import re
from os import makedirs, path
from markdown import markdown
from datetime import datetime

pybb = "pybb.db"
outdir = "blog"
index_len = 10
debug = True
#break_re = r'<hr\s*\/?>'
break_re = r'[*-_]( *[*-_]){2,}'

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

def geturi(filename, pd):
    return pd[0:4] + "/" + pd[5:7] + "/" + filename

def pubdate2str(pubdate, formatstr):
    pd = datetime.strptime(pubdate, "%Y-%m-%d %H:%M:%S")
    return pd.strftime(formatstr)

conn = sqlite3.connect(pybb)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("PRAGMA foreign_keys=1")

# Get everything from post content up to the break
# If there is no break, return the whole thing
# Return string is HTML
def getsummary(content):
    p = re.compile(break_re)
    is_summary = False
    ret = ""
    for r in content.splitlines():
        if p.match(r):
            is_summary = True
            break
        else:
            ret += r
    return is_summary, markdown(ret)

# Make blog index
def makeindex():
    makedirs(outdir, exist_ok=True)
    idxf = open(outdir + "/index.html", 'w+', encoding="utf-8")
    
    idxf.write(header)
    for row in cur.execute("SELECT title, publish_date, filename, content "
                           "FROM posts ORDER BY publish_date DESC LIMIT ?",
                           (index_len,)):
        pdstring = pubdate2str(row["publish_date"], dateformat)
        datedir = path.join(row["publish_date"][0:4], row["publish_date"][5:7])
        outfile = path.join(datedir, row["filename"])
        is_summary, summary = getsummary(row["content"])
        idxf.write("<h3><a href=\"{outfile}\">{title}</a></h3>\n"
                   "<p>{publish_date}</p>\n{summary}"
                    .format(outfile=outfile,
                            publish_date=pdstring,
                            title=row["title"],
                            summary=summary))
        if is_summary: idxf.write("<p><a href=\"{}\">Read more...</a></p>\n"
                                  .format(outfile))
        if debug: print(".", end="")
    idxf.write(footer)
    if debug: print("")
    idxf.close()

# Write posts to files
def writeposts():
    for row in cur.execute("SELECT title, publish_date, filename, content "
                       "FROM posts"):
        pdstring = pubdate2str(row["publish_date"], dateformat)
        datedir = path.join(row["publish_date"][0:4], row["publish_date"][5:7])
        makedirs(path.join(outdir, datedir), mode=0o750, exist_ok=True)
        outfile = path.join(outdir, datedir, row["filename"])
        # Write each post file
        with open(outfile, 'w', encoding="utf-8") as f:
            f.write(header)
            f.write("<h1>" + row["title"] + "</h1>\n" + "<p>" + pdstring + "</p>\n")
            f.write(markdown(row["content"]))
            f.write(footer)
        if debug: print(".", end="")
    if debug: print("")

# Make full index
def makefullidx():
    makedirs(outdir, exist_ok=True)
    f = open(outdir + "/all_posts.html", 'w', encoding="utf-8")
    f.write(header)
    prevmonth = None
    for row in cur.execute("SELECT title, publish_date, filename "
                           "FROM posts ORDER BY publish_date DESC"):
        pd = datetime.strptime(row["publish_date"], "%Y-%m-%d %H:%M:%S")
        thismonth = (pd.year, pd.month)
        # if prevmonth is None: f.write("<ul>\n");
        if thismonth != prevmonth:
            if prevmonth is not None: f.write("</ul>\n")
            f.write("<h2>" + pubdate2str(row["publish_date"], "%B %Y") + "</h2>\n<ul>")
        f.write("<li><a href=\"%s\">%s</a> &mdash; %s</li>" %
                (geturi(row["filename"], row["publish_date"]),
                 row["title"], pubdate2str(row["publish_date"], dateformat)
                 )
                )
        prevmonth = thismonth
        if debug: print(".", end="")
    f.write("</ul>")
    f.write(footer)
    f.close()
    if debug: print("")

# Make alphabetical list of all tags
def maketagindex():
    makedirs(outdir, exist_ok=True)
    f = open(outdir + "/all_tags.html", 'w', encoding="utf-8")
    f.write(header)
    f.write("<ul>")
    for row in cur.execute("SELECT text, COUNT(tags_ref.tag_id) as count "
                           "FROM tags, tags_ref "
                           "WHERE tags.tag_id = tags_ref.tag_id "
                           "GROUP BY tags_ref.tag_id ORDER BY text ASC"):
        f.write("<li><a href=\"tag_%s\">%s</a>"
                " &mdash; %d posts" % (row["text"], row["text"], row["count"]))
        if debug: print(".", end="")
    f.write("</ul>")
    if debug: print("")

# Make a page for each tag
def maketagpages():
    makedirs(outdir, exist_ok=True)
    tagfiles = {}
    for row in cur.execute("SELECT tags.text AS tag, posts.title AS title, "
                           "posts.filename AS fn, posts.publish_date AS pd, "
                           "posts.content AS content "
                           "FROM posts, tags, tags_ref "
                           "WHERE tags_ref.post_id = posts.post_id "
                           "AND tags_ref.tag_id = tags.tag_id "
                           "ORDER BY tags.text ASC, posts.publish_date DESC"):
        tagpath = path.join(outdir, "tag_" + row["tag"] + ".html")
        if tagpath not in tagfiles.keys():
            tagfiles[tagpath] = open(tagpath, 'w')
            tagfiles[tagpath].write(header)
        postpath = geturi(row["fn"],  row["pd"])
        pdstring = pubdate2str(row["pd"], dateformat)
        tagfiles[tagpath].write("<a href=\"" + postpath + "\"</a>" +
                                "<h3>" + row["title"] + "</h3></a>\n")
        tagfiles[tagpath].write("<p>" + pdstring + "</p>\n")
        if debug: print(".", end="")
    for p, f in tagfiles.items():
        f.write(footer)
        f.close()
    if debug: print("")

# Invoke functions from here

if debug: print("Writing posts ", end = "")
writeposts()
if debug: print("Creating index.html ", end = "")
makeindex()
if debug: print("Creating all_posts.html ", end = "")
makefullidx()
if debug: print("Creating all_tags.html ", end = "")
maketagindex()
if debug: print("Creating tag_*.html ", end = "")
maketagpages()

if debug: print("Done.")
conn.close()