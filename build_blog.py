#!/usr/bin/env python3

import sqlite3, locale, re, click
from os import makedirs, path
from markdown import markdown
from datetime import datetime

pybb = "pybb.db"
outdir = "blog"
index_len = 10
debug = True
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
    """
    Get a post's URI. Arguments are the post's filename and publish_date.
    This URI is for linking from other pages in the blog.
    """

    return pd[0:4] + "/" + pd[5:7] + "/" + filename

def pubdate2str(pubdate, formatstr):
    pd = datetime.strptime(pubdate, "%Y-%m-%d %H:%M:%S")
    return pd.strftime(formatstr)

def getsummary(content):
    """
    Get everything from post content up to the break.
    If there is no break, return the whole thing.
    Return string is HTML.
    """

    p = re.compile(break_re)
    is_summary = False
    ret = ""
    for r in content.splitlines(keepends=True):
        if p.match(r):
            is_summary = True
            break
        else:
            ret += r
    return is_summary, markdown(ret)

def gettagsline(post_id, prefix=""):
    """Get the tags for a post by id"""

    tags = []
    for r in cur.execute("SELECT tags.text AS tag FROM tags, posts, tags_ref "
                         "WHERE tags.tag_id = tags_ref.tag_id AND "
                         "posts.post_id = tags_ref.post_id AND "
                         "posts.post_id = ?", (post_id,)):
        tags.append(r[0])
    ret = ""
    for i, t in enumerate(tags):
        if i == 0:
            ret += ("<a href=\"{prefix}tag/{tag}.html\">{tag}</a>").\
            format(tag=t, prefix=prefix)
        else:
            ret += (" <a href=\"{prefix}tag/{tag}.html\">{tag}</a>").\
            format(tag=t, prefix=prefix)
    return ret

def makeindex():
    """Make the main index.html"""

    makedirs(outdir, exist_ok=True)
    idxf = open(outdir + "/index.html", 'w+', encoding="utf-8")

    idxf.write(header)
    cur.execute("SELECT post_id, title, publish_date, filename, content "
                "FROM posts ORDER BY publish_date DESC LIMIT ?",
                (index_len,))
    for row in cur.fetchall():
        pdstring = pubdate2str(row["publish_date"], dateformat)
        outfile = geturi(row["filename"], row["publish_date"])
        is_summary, summary = getsummary(row["content"])
        idxf.write("<h3><a href=\"{outfile}\">{title}</a></h3>\n"
                   "<p>{publish_date}</p>\n{summary}"
                    .format(outfile=outfile,
                            publish_date=pdstring,
                            title=row["title"],
                            summary=summary))
        if is_summary: idxf.write("<p><a href=\"{}\">Read more...</a></p>\n"
                                  .format(outfile))

        idxf.write("<p>Luokat: {}</p>\n".format(gettagsline(row["post_id"])))

        if debug: click.echo(".", end="")
    idxf.write(footer)
    if debug: click.echo("")
    idxf.close()

def writeposts():
    """Write posts to files. Also make any necessary subdirectories."""

    cur.execute("SELECT post_id, title, publish_date, filename, content "
                "FROM posts")
    for row in cur.fetchall():
        pdstring = pubdate2str(row["publish_date"], dateformat)
        datedir = path.join(row["publish_date"][0:4], row["publish_date"][5:7])
        makedirs(path.join(outdir, datedir), mode=0o750, exist_ok=True)
        outfile = path.join(outdir, datedir, row["filename"])
        # Write each post file
        with open(outfile, 'w', encoding="utf-8") as f:
            f.write(header)
            f.write("<h1>" + row["title"] + "</h1>\n" + "<p>" + pdstring + "</p>\n")
            f.write(markdown(row["content"]))
            f.write("<p>Luokat: {}</p>\n".
                    format(gettagsline(row["post_id"], "../../")))
            f.write(footer)
        if debug: click.echo(".", end="")
    if debug: click.echo("")

def makefullidx():
    """Make an index page listing all posts"""

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
        if debug: click.echo(".", end="")
    f.write("</ul>")
    f.write(footer)
    f.close()
    if debug: click.echo("")

def maketagindex():
    """Make alphabetical list of all tags"""

    makedirs(outdir, exist_ok=True)
    f = open(outdir + "/all_tags.html", 'w', encoding="utf-8")
    f.write(header)
    f.write("<ul>")
    for row in cur.execute("SELECT text, COUNT(tags_ref.tag_id) as count "
                           "FROM tags, tags_ref "
                           "WHERE tags.tag_id = tags_ref.tag_id "
                           "GROUP BY tags_ref.tag_id ORDER BY text ASC"):
        f.write("<li><a href=\"tag/%s.html\">%s</a>"
                " &mdash; %d posts" % (row["text"], row["text"], row["count"]))
        if debug: click.echo(".", end="")
    f.write("</ul>")
    if debug: click.echo("")

def maketagpages():
    """Make a page for each tag"""

    tagdir = path.join(outdir, "tag")
    makedirs(tagdir, exist_ok=True)
    tagfiles = {}
    cur.execute("SELECT tags.text AS tag, posts.title AS title, "
                "posts.filename AS fn, posts.publish_date AS pd, "
                "posts.content AS content, "
                "posts.post_id AS post_id "
                "FROM posts, tags, tags_ref "
                "WHERE tags_ref.post_id = posts.post_id "
                "AND tags_ref.tag_id = tags.tag_id "
                "ORDER BY tags.text ASC, posts.publish_date DESC")
    for row in cur.fetchall():
        tagpath = path.join(tagdir, row["tag"] + ".html")
        if tagpath not in tagfiles.keys():
            tagfiles[tagpath] = open(tagpath, 'w')
            tagfiles[tagpath].write(header)
        postpath = "../" + geturi(row["fn"],  row["pd"])
        pdstring = pubdate2str(row["pd"], dateformat)
        has_summary, summary = getsummary(row["content"])
        tagfiles[tagpath].write("<h3><a href=\"{outfile}\">{title}</a></h3>\n"
                       "<p>{publish_date}</p>\n{summary}\n"
                       .format(outfile=postpath,
                                publish_date=pdstring,
                                title=row["title"],
                                summary=summary))
        if has_summary: tagfiles[tagpath].write(
            "<p><a href=\"{}\">Read more...</a></p>\n"
            .format(postpath))

        tagfiles[tagpath].write("<p>Luokat: {}</p>\n".
                                format(gettagsline(row["post_id"], "../")))

        if debug: click.echo(".", end="")
    for p, f in tagfiles.items():
        f.write(footer)
        f.close()
    if debug: click.echo("")

# Click stuff

@click.group(context_settings=dict(help_option_names=['-h', '--help']))
@click.version_option()
def cli():
    """A static blog generator."""
    pass

@click.command()
@click.argument("dir",
                 required=False,
                 type=click.Path(dir_okay=True, writable=True))
def init(dir):
    """Initialize a new blog.

    This creates an empty database file.
    By default the current working directory is used,
    but you can optionally provide a different one.
    """
    if not dir: dir = "."
    click.echo("Initializing a new blog in `%s'" % dir)

@click.command()
@click.option('--hidden', is_flag=True,
               help="Make this post hidden (a draft).")
@click.option('--input', '-i', type=click.File('r'),
               help="Read post content from file (don't open an editor).")
def post(hidden, input):
    """Write a new blog post."""
    click.echo("Make a new post")

@click.command(name="ls")
@click.option('--order-by',
               type=click.Choice(['id', 'title', 'date']),
               help="Select which field to order by (default=date).")
@click.option('--asc','collation', flag_value='ASC', default=False,
               help="Ascending order.")
@click.option('--desc','collation', flag_value='DESC', default=True,
               help="Descending order (default).")
def list_posts(order_by, collation):
    """List all blog posts."""

    # Get terminal width and height
    tw, th = click.get_terminal_size()
    rowstr = "{:>6} | {:<19} | {:<25}"
    # Print a '-' separator with '+' signs at column borders,
    # fill to terminal width
    separator = "-"*6 + "-+-" + "-"*19 + "-+-"
    separator += "-"*(tw-len(separator))
    query = "SELECT post_id, publish_date, title FROM posts ORDER BY publish_date DESC"
    if order_by == "date" or order_by is None:
        order_by = "publish_date"
    click.echo("query was:\n" + query)
    click.echo(rowstr.format("ID", "Date", "Title"))
    click.echo(separator)
    for row in cur.execute(query):#,(order_by,)):
        click.echo(rowstr.format(row["post_id"], row["publish_date"],
                   row["title"]))

@click.command()
@click.argument('id', type=click.INT)
def edit(id):
    """Edit a post with given ID."""

    postquery = "SELECT title, content FROM posts WHERE post_id = ?"
    cur.execute(postquery,(id,))
    try:
        title, content = cur.fetchone()
    except:
        raise click.BadParameter("No post found with ID %d" % id)
    tagquery = """SELECT text AS tag FROM tags, tags_ref WHERE
    tags_ref.post_id = ? AND tags.tag_id = tags_ref.tag_id
    ORDER BY tag"""
    cur.execute(tagquery, (id,))
    tagsline = "Luokat: "
    tagslist = (r[0] for r in cur.fetchall())
    if tagslist is not None:
        tagsline += ", ".join(tagslist)
    print(tagsline)
    content += tagsline
    new_content = click.edit(text=(title + "\n" + content),
        extension=".md", require_save=True)

    if new_content is not None:
        click.echo("Congrats, you've made an edit!")
    else:
        click.echo("Edit aborted.")

@click.command()
@click.argument('id', type=click.INT)
def hide(id):
    """Flag a post with given ID as hidden."""
    click.echo("Hide a post")

@click.command()
@click.argument('id', type=click.INT)
def unhide(id):
    """Flag a post with given ID as not hidden."""
    click.echo("Unhide a post")

@click.command()
def publish():
    """Upload the blog.

    Copies the blog to the configured
    location using rsync."""
    click.echo("Publish a post")

@click.command()
@click.argument('id', type=click.INT)
def rm():
    """Remove a post with given ID. The post is deleted from both
    the directory tree and the database.

    Remember that you can also hide posts. This retains the data in
    the database, in case you want to use it again later.
    """

@click.command()
def rebuild():
    """Rebuild all posts and tags.

    This can be used to recreate
    the blog from e.g. a database backup if something's gone wrong."""

@click.command()
@click.argument('file', nargs=-1)
def bb_import(file):
    """Import posts from Bashblog Markdown files.

    Arguments are a list of Markdown files.
    """

cli.add_command(post)
cli.add_command(list_posts)
cli.add_command(edit)
cli.add_command(hide)
cli.add_command(unhide)
cli.add_command(publish)
cli.add_command(rm)
cli.add_command(rebuild)
cli.add_command(init)
cli.add_command(bb_import)

if __name__ == '__main__':
    conn = sqlite3.connect(pybb)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys=1")
    cli()
    conn.close()

