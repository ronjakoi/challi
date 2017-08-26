#!/usr/bin/env python3

import configparser
import locale
import re
import sqlite3
from os import makedirs, path
from datetime import datetime, timezone
from markdown import markdown
import click

pybb = "pybb.db"
debug = True
break_re = r'[*-_]( *[*-_]){2,}'
config_file = "config.ini"


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

    cur_inner = conn.cursor()
    cur_inner.execute("SELECT tags.text AS tag FROM tags, posts, tags_ref "
                      "WHERE tags.tag_id = tags_ref.tag_id AND "
                      "posts.post_id = tags_ref.post_id AND "
                      "posts.post_id = ?", (post_id,))
    return ", ".join("<a href=\"{prefix}tag/{tag}.html\">{tag}</a>".
                     format(tag=r[0], prefix=prefix) for r in cur_inner)


def split_input(post_text):
    body = ""
    for i, line in enumerate(post_text.splitlines()):
        if i == 0:
            title = line.strip()
        elif line.startswith("{}: "):
            tags = line.strip().replace("{} ".format(tags_text), "", 1).split(", ")
        else:
            body += line + "\n"
    return title, body, tags


def makeindex():
    """Make the main index.html"""

    makedirs(outdir, exist_ok=True)
    idxf = open(path.join(outdir,
                          config.get("files", "index_file", fallback="index.html")),
                          'w+', encoding="utf-8")

    idxf.write(header)
    cur.execute("SELECT post_id, title, publish_date, filename, content "
                "FROM posts ORDER BY publish_date DESC LIMIT ?",
                (index_len,))
    with click.progressbar(cur, label="Making index.html", width=0) as posts:
        for row in posts:
            pdstring = pubdate2str(row["publish_date"], dateformat)
            outfile = geturi(row["filename"], row["publish_date"])
            is_summary, summary = getsummary(row["content"])
            idxf.write("<h3><a href=\"{outfile}\">{title}</a></h3>\n"
                       "<p>{publish_date}</p>\n{summary}"
                       .format(outfile=outfile,
                               publish_date=pdstring,
                               title=row["title"],
                               summary=summary))
            if is_summary:
                idxf.write("<p><a href=\"{}\">{}</a></p>\n"
                           .format(outfile,
                                   config.get("template", "read_more", fallback="Read more...")))
            idxf.write("<p>{} {}</p>\n".format(tags_text, gettagsline(row["post_id"])))
    idxf.write(footer)
    idxf.close()


def writeposts():
    """Write posts to files. Also make any necessary subdirectories."""

    cur.execute("SELECT post_id, title, publish_date, filename, content "
                "FROM posts")
    with click.progressbar(cur, label="Writing posts", width=0) as posts:
        for row in posts:
            pdstring = pubdate2str(row["publish_date"], dateformat)
            datedir = path.join(row["publish_date"][0:4], row["publish_date"][5:7])
            makedirs(path.join(outdir, datedir), mode=0o750, exist_ok=True)
            outfile = path.join(outdir, datedir, row["filename"])
            # Write each post file
            with open(outfile, 'w', encoding="utf-8") as f:
                f.write(header)
                f.write("<h1>" + row["title"] + "</h1>\n" + "<p>" + pdstring + "</p>\n")
                f.write(markdown(row["content"]))
                f.write("<p>{} {}</p>\n".
                        format(config.get("template", "tags_line_header", fallback="Tags:"),
                               gettagsline(row["post_id"], "../../")))
                f.write(footer)


def makefullidx():
    """Make an index page listing all posts"""

    makedirs(outdir, exist_ok=True)
    archive_index = config.get("files", "archive_index", fallback="all_posts.html")
    f = open(path.join(outdir, archive_index),
             'w', encoding="utf-8")
    f.write(header)
    prevmonth = None
    cur.execute("SELECT title, publish_date, filename "
                "FROM posts ORDER BY publish_date DESC")

    with click.progressbar(cur, label="Making %s" % archive_index, width=0) as posts:
        for row in posts:
            pd = datetime.strptime(row["publish_date"], "%Y-%m-%d %H:%M:%S")
            thismonth = (pd.year, pd.month)
            if thismonth != prevmonth:
                if prevmonth is not None:
                    f.write("</ul>\n")
                f.write("<h2>" + pubdate2str(row["publish_date"], "%B %Y") + "</h2>\n<ul>")
            f.write("<li><a href=\"%s\">%s</a> &mdash; %s</li>" %
                    (geturi(row["filename"], row["publish_date"]),
                     row["title"],
                     pubdate2str(row["publish_date"], dateformat))
                    )
            prevmonth = thismonth
    f.write("</ul>" + footer)
    f.close()


def maketagindex():
    """Make alphabetical list of all tags"""

    makedirs(outdir, exist_ok=True)
    tag_index = config.get("files", "tags_index", fallback="all_tags.html")
    f = open(path.join(outdir, tag_index), 'w', encoding="utf-8")
    f.write(header)
    f.write("<ul>")
    cur.execute("SELECT text, COUNT(tags_ref.tag_id) as count "
                "FROM tags, tags_ref "
                "WHERE tags.tag_id = tags_ref.tag_id "
                "GROUP BY tags_ref.tag_id ORDER BY text ASC")
    with click.progressbar(cur, label="Making all_tags.html", width=0) as tags:
        for row in tags:
            f.write("<li><a href=\"tag/%s.html\">%s</a>"
                    " &mdash; %d posts" % (row["text"], row["text"], row["count"]))
    f.write("</ul>")
    f.close()


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
    with click.progressbar(cur, label="Making tag/*.html", width=0) as tags:
        for row in tags:
            tagpath = path.join(tagdir, row["tag"] + ".html")
            if tagpath not in tagfiles.keys():
                tagfiles[tagpath] = open(tagpath, 'w')
                tagfiles[tagpath].write(header)
            postpath = "../" + geturi(row["fn"], row["pd"])
            pdstring = pubdate2str(row["pd"], dateformat)
            has_summary, summary = getsummary(row["content"])
            tagfiles[tagpath].write("<h3><a href=\"{outfile}\">{title}</a></h3>\n"
                                    "<p>{publish_date}</p>\n{summary}\n"
                                    .format(outfile=postpath,
                                            publish_date=pdstring,
                                            title=row["title"],
                                            summary=summary))
            if has_summary:
                tagfiles[tagpath].write("<p><a href=\"{}\">Read more...</a></p>\n"
                                        .format(postpath))

            tagfiles[tagpath].write("<p>{} {}</p>\n".
                                    format(tags_text, gettagsline(row["post_id"], "../")))
    for f in tagfiles.values():
        f.write(footer)
        f.close()


def db_tagpost(tags, post_id):
    # Delete all tag-post relations for this post. Needed for updates.
    cur.execute("DELETE FROM tags_ref WHERE post_id = ?", (post_id,))
    for tag in tags:
        # Check if a tag with this text already exists
        cur.execute("SELECT tag_id FROM tags WHERE text = ?", (tag,))
        try:
            tag_id = cur.fetchone()[0]
        # If not, insert it
        except TypeError:  # fetchone() returns None if no more rows
            cur.execute("INSERT INTO tags (text) VALUES (?)", (tag,))
            tag_id = cur.lastrowid
        # Insert a relation tag <-> post
        cur.execute("INSERT INTO tags_ref (tag_id, post_id) VALUES (?, ?)",
                    (tag_id, post_id))


def db_rm_orphan_tags():
    cur.execute("DELETE FROM tags"
                "WHERE NOT EXISTS(SELECT 1 FROM tags_ref WHERE tags_ref.tag_id = tags.tag_id)")


def set_post_hidden(id_, hidden):
    """Set the hidden status of a post."""
    cur.execute("UPDATE posts SET hidden = ? WHERE id = ?", (hidden, id_))
    conn.commit()


# Click stuff


@click.group(context_settings=dict(help_option_names=['-h', '--help']))
@click.version_option()
def cli():
    """A static blog generator."""
    pass


@click.command()
@click.argument("directory",
                required=False,
                type=click.Path(dir_okay=True, writable=True))
def init(directory):
    """Initialize a new blog.

    This creates an empty database file.
    By default the current working directory is used,
    but you can optionally provide a different one.
    """
    if not directory:
        directory = "."
    init_db = path.join(directory, pybb)
    if path.isfile(init_db):
        raise click.Abort("Database file `%s' exists" % init_db)

    click.echo("Initializing empty database in `%s'..." % init_db)
    init_conn = sqlite3.connect(init_db)
    init_cur = init_conn.cursor()
    init_sql = """
    BEGIN TRANSACTION;
    -- Relation table: tag <-> post
    CREATE TABLE `tags_ref` (
        `tag_ref_id`	INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE,
        `tag_id`	INTEGER NOT NULL,
        `post_id`	INTEGER NOT NULL,
        FOREIGN KEY(`tag_id`) REFERENCES tags("tag_id") ON DELETE CASCADE,
        FOREIGN KEY(`post_id`) REFERENCES posts("post_id") ON DELETE CASCADE,
        CONSTRAINT `tag_post_unique` UNIQUE (`tag_id`, `post_id`)
    );
    -- One row for each tag
    CREATE TABLE `tags` (
        `tag_id`	INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE,
        `text`	TEXT NOT NULL UNIQUE
    );
    -- Posts
    CREATE TABLE "posts" (
        `post_id`	INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE,
        `title`	TEXT NOT NULL,
        `content`	TEXT,
        -- ISO-8601 timestamp string, UTC
        `publish_date`	TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        `hidden`	INTEGER NOT NULL DEFAULT 1,
        `filename`	TEXT NOT NULL
    );
    -- Authors
    CREATE TABLE "authors" (
        `author_id`	INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE,
        `name` TEXT NOT NULL,
        `email` TEXT,
        `avatar_uri` TEXT,
        `description` TEXT
    );
    -- Relation table: authors <-> posts
    CREATE TABLE `authors_ref` (
        `author_ref_id`	INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE,
        `author_id`	INTEGER NOT NULL,
        `post_id`	INTEGER NOT NULL,
        FOREIGN KEY(`author_id`) REFERENCES authors("author_id"),
        FOREIGN KEY(`post_id`) REFERENCES posts("post_id") ON DELETE CASCADE
    );
    CREATE INDEX `post_pub_date` ON `posts` (`publish_date` DESC);
    CREATE INDEX `author_name` ON `authors` (`name` ASC);
    CREATE UNIQUE INDEX `tag_ref_i` ON `tags_ref`(`tag_id`, `post_id`);
    COMMIT;
    """

    init_cur.execute(init_sql)


@click.command()
@click.option('--hidden', is_flag=True,
              help="Make this post hidden (a draft).")
@click.option('--get-from', '-g', type=click.File('r'),
              help="Read post content (and tags) from file (don't open an editor).")
def post(hidden, get_from):
    """Write a new blog post."""

    post_template = \
        ("This line is your title\n\n"
         "The body of your post goes here.\n\n"
         "{} comma-separated, list, of, tags").format(tags_text)

    query = """INSERT INTO posts
            (title, content, publish_date, filename, hidden)
            VALUES (?, ?, ?, ?, ?)"""

    pd = datetime.strftime(datetime.now(timezone.utc), "%Y-%m-%d %H:%M:%S")

    if get_from:
        post_text = get_from.read()
    else:
        post_text = click.edit(text=post_template, extension=".md",
                               require_save=True)
    if post_text is None or post_text == post_template:
        raise click.UsageError("No edits made to template")

    title, body, tags = split_input(post_text)

    fromchars = "äöåøæđðčžš"
    tochars   = "aoaoaddczs"
    transtable = str.maketrans(fromchars, tochars)

    filename = title.replace(" ", "_").lower()
    filename = re.sub(r'[^\w\d]', "", filename).strip('_') + ".html"
    filename = filename.translate(transtable)

    cur.execute(query, (title, body, pd, filename, hidden))
    post_id = cur.lastrowid

    db_tagpost(tags, post_id)
    rebuild()


@click.command(name="ls")
@click.option('--order-by',
              type=click.Choice(['id', 'title', 'date']),
              help="Select which field to order by (default=date).")
@click.option('--asc', 'collation', flag_value='ASC', default=False,
              help="Ascending order.")
@click.option('--desc', 'collation', flag_value='DESC', default=True,
              help="Descending order (default).")
def list_posts(order_by, collation):
    """List all blog posts."""

    # TODO: --order-by and --asc/--desc do nothing right now.
    # Wasn't working when I tried :(

    # Get terminal width and height
    tw, th = click.get_terminal_size()
    rowstr = "{:>6} | {:>16} | {:>6} | {:<25}"
    # Print a '-' separator with '+' signs at column borders,
    # fill to terminal width
    separator = "-"*6 + "-+-" + "-"*16 + "-+--------+-"
    separator += "-"*(tw-len(separator))
    query = """SELECT post_id, publish_date, title, hidden FROM
    posts ORDER BY publish_date DESC"""
    if order_by == "date" or order_by is None:
        order_by = "publish_date"
    list_text = rowstr.format("ID", "Date", "Hidden", "Title") + "\n"
    list_text += separator + "\n"
    for row in cur.execute(query):#,(order_by,)):
        if row["hidden"]:
            hidden = "✔"
        else:
            hidden = " "
        date = row["publish_date"][:16]
        list_text += rowstr.format(row["post_id"], date,
                                   hidden, row["title"]) + "\n"
    if list_text.count("\n") + 1 > th:
        click.echo_via_pager(list_text)
    else:
        click.echo(list_text)


@click.command()
@click.argument('id_', type=click.INT, metavar='ID')
def edit(id_):
    """Edit a post with given ID."""

    tagquery = """SELECT text AS tag FROM tags, tags_ref WHERE
    tags_ref.post_id = ? AND tags.tag_id = tags_ref.tag_id
    ORDER BY tag"""
    postquery = "SELECT title, content FROM posts WHERE post_id = ?"
    updatequery = """UPDATE posts SET title = ?, content = ?
                  WHERE post_id = ?"""
    cur.execute(postquery, (id_,))
    try:
        title, content = cur.fetchone()
    except:
        raise click.BadParameter("No posts found.", param=id_, param_hint="ID")

    cur.execute(tagquery, (id_,))
    tagsline = "{} ".format(tags_text)
    tagslist = (r[0] for r in cur)
    if tagslist is not None:
        tagsline += ", ".join(tagslist)
    content += tagsline
    new_content = click.edit(text=(title + "\n" + content),
                             extension=".md", require_save=True)

    if new_content is not None:
        title, body, tags = split_input(new_content)
        cur.execute(updatequery, (title, body, id_))
        db_tagpost(tags, id_)
        rebuild()
    else:
        raise click.UsageError("No edits made to template")


@click.command()
@click.argument('id_', type=click.INT, metavar='ID')
def hide(id_):
    """Flag a post with given ID as hidden."""
    set_post_hidden(id_, True)
    rebuild()


@click.command()
@click.argument('id_', type=click.INT, metavar='ID')
def unhide(id_):
    """Flag a post with given ID as not hidden."""
    set_post_hidden(id_, False)
    rebuild()


@click.command()
def publish():
    """Upload the blog.

    Copies the blog to the configured
    location using rsync."""
    click.echo("Publish a post")


@click.command()
@click.argument('id_', type=click.INT, metavar='ID')
def rm(id_):
    """Remove a post with given ID. The post is deleted from both
    the directory tree and the database.

    Remember that you can also hide posts. This retains the data in
    the database, in case you want to use it again later.
    """
    import os

    try:
        pd, fn = next(cur.execute("SELECT publish_date, filename FROM posts WHERE post_id = ?", (id_,)))
    except:
        raise click.BadParameter("No posts found.", param=id_, param_hint="ID")
    else:
        # Remove the file
        os.remove(path.join(outdir, geturi(fn, pd)))
        #print(path.join(outdir, geturi(fn, pd)))
        # Attempt to prune the directory tree the file was in
        try:
            os.removedirs(path.join(outdir, path.dirname(geturi(fn, pd))))
        except OSError:
            pass
        cur.execute("DELETE FROM posts WHERE post_id = ?", (id_,))
        conn.commit()
        click.echo("Deleted post with id {}".format(id_))
        rebuild()


@click.command()
def rebuild():
    """Rebuild all posts, tags and indexes."""
    writeposts()
    makeindex()
    makefullidx()
    maketagpages()
    maketagindex()


@click.command()
@click.argument('file', nargs=-1)
def bb_import(file):
    """Import posts from Bashblog Markdown files.

    Arguments are a list of Markdown files.
    """
    pass

for func in post, list_posts, edit, hide, unhide, publish, rm, rebuild, init:
    cli.add_command(func)

# cli.add_command(bb_import)

if __name__ == '__main__':
    # Setting up Sqlite connection
    conn = sqlite3.connect(pybb)
    conn.row_factory = sqlite3.Row

    # Reading config from INI file
    config = configparser.ConfigParser()
    config.read(config_file, encoding="utf-8")
    locale.setlocale(locale.LC_ALL,
                     config.get("template", "date_locale", fallback="C"))
    dateformat = config.get("template", "date_format", fallback="%B %d, %Y")
    index_len = config.getint("files", "number_of_index_articles", fallback=8)
    outdir = config.get("files", "blog_dir", fallback=".")
    tags_text = config.get("template", "tags_line_header", fallback="Tags:")
    header_file = config.get("files", "header_file", fallback=None)
    footer_file = config.get("files", "footer_file", fallback=None)
    if header_file:
        with open(header_file, "r", encoding="utf-8") as hf:
            header = hf.read()
    else:
        header = \
            ("<!doctype html>\n"
             "<html>\n"
             "<head>\n"
             "    <meta charset=\"utf-8\" />\n"
             "    <title>This is a blog</title>\n"
             "</head>\n"
             "<body>\n")
    if footer_file:
        with open(footer_file, "r", encoding="utf-8") as ff:
            footer = ff.read()
    else:
        footer = "\n</body></html>"

    try:
        with conn:
            # Setting up Sqlite things some more
            cur = conn.cursor()
            cur.execute("PRAGMA foreign_keys=1")
            # Starting command line interface and parsing commands through Click
            cli()
    except sqlite3.IntegrityError as e:
        click.echo("SQL error: %s" % e)
