#!/usr/bin/env python3

import configparser
import locale
import re
import sqlite3
from os import makedirs, path, system

from datetime import datetime, timezone
from typing import Tuple
from markdown import markdown
import click

db_file = "challi.db"
"""Sqlite3 database file."""

break_re = r'[*-_]( *[*-_]){2,}'
"""Regular expression used to determine summary breaks in Markdown."""

config_file = "config.ini"
blog_conf = None
cur = None
conn = None
index_len = None
header, footer = "", ""

def makeheader() -> str:
    h1 = """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml"><head>
<meta http-equiv="Content-type" content="text/html;charset=UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />"""

    for css in blog_conf["files"]["css_include"].split(","):
        h1 += "<link rel=\"stylesheet\" href=\"{}\" type=\"text/css\" />".\
            format(css.strip())

    h2 = """<title>{title}</title>
    </head><body>
    <div id="divbodyholder">
    <div class="headerholder"><div class="header">
    <div id="title">
    <h1 class="nomargin"><a class="ablack" href="{url}">{title}</a></h1>
    <div id="description">{description}</div>
    </div></div></div>
    <div id="divbody"><div class="content">"""

    return h1 + h2


def makefooter() -> str:
    f = """<div id="all_posts">
    <a href="/all_posts.html">{all_posts}</a> &mdash;
    <a href="/all_tags.html">{all_tags}</a>
    </div>
    <div id="footer">&copy; <a href="{author_url}">{author_name}</a> &mdash;
    <a href="mailto:{author_email}">{author_email}</a><br/>
    </div>
    </div></div>
    </body></html>"""
    return f


def geturi(filename: str, pd: str) -> str:
    """Get a post's URI. Arguments are the post's filename and publish_date.

    This URI is for linking from other pages in the blog."""

    return pd[0:4] + "/" + pd[5:7] + "/" + filename


def pubdate2str(pubdate, formatstr: str) -> str:
    pd = datetime.strptime(pubdate, "%Y-%m-%d %H:%M:%S")
    return pd.strftime(formatstr)


def getsummary(content: str) -> Tuple:
    """Get everything from post content up to the break, returning a boolean and an HTML string.

    If there is no break, return the whole thing."""

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


def gettagsline(post_id: int, prefix: str = "") -> str:
    """Get the tags for a post by id"""

    cur_inner = conn.cursor()
    cur_inner.execute("SELECT tags.text AS tag FROM tags, posts, tags_ref "
                      "WHERE tags.tag_id = tags_ref.tag_id AND "
                      "posts.post_id = tags_ref.post_id AND "
                      "posts.post_id = ?", (post_id,))
    return ", ".join("<a href=\"{prefix}tag/{tag}.html\">{tag}</a>".
                     format(tag=r[0], prefix=prefix) for r in cur_inner)


def split_input(post_text: str) -> Tuple:
    body = ""
    for i, line in enumerate(post_text.splitlines()):
        if i == 0:
            title = line.strip()
        elif line.startswith("{} ".format(blog_conf["template"]["tags_line_header"])):
            tags = line.strip(). \
                replace("{} ".format(blog_conf["template"]["tags_line_header"]), "", 1). \
                split(", ")
        else:
            body += line + "\n"
    return title, body, tags


def makeindex():
    """Make the main index.html"""

    makedirs(blog_conf["files"]["blog_dir"], exist_ok=True)
    idxf = open(path.join(blog_conf["files"]["blog_dir"],
                          blog_conf.get("files", "index_file", fallback="index.html")),
                'w+', encoding="utf-8")

    idxf.write(header)
    cur.execute("SELECT post_id, title, publish_date, filename, content "
                "FROM posts ORDER BY publish_date DESC LIMIT ?",
                (index_len,))
    with click.progressbar(cur, label="Making index.html", width=0) as posts:
        for row in posts:
            pdstring = pubdate2str(row["publish_date"],
                                   blog_conf["template"]["date_format"])
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
                                   blog_conf.get("template", "read_more", fallback="Read more...")))
            idxf.write("<p>{} {}</p>\n".
                       format(blog_conf["template"]["tags_line_header"],
                              gettagsline(row["post_id"])))
    idxf.write(footer)
    idxf.close()


def writeposts():
    """Write posts to files. Also make any necessary subdirectories."""

    cur.execute("SELECT post_id, title, publish_date, filename, content "
                "FROM posts")
    with click.progressbar(cur, label="Writing posts", width=0) as posts:
        for row in posts:
            pdstring = pubdate2str(row["publish_date"],
                                   blog_conf["template"]["date_format"])
            datedir = path.join(row["publish_date"][0:4], row["publish_date"][5:7])
            makedirs(path.join(blog_conf["files"]["blog_dir"], datedir),
                     mode=0o750, exist_ok=True)
            outfile = path.join(blog_conf["files"]["blog_dir"], datedir, row["filename"])
            # Write each post file
            with open(outfile, 'w', encoding="utf-8") as f:
                f.write(header)
                f.write("<h1>" + row["title"] + "</h1>\n" + "<p>" + pdstring + "</p>\n")
                f.write(markdown(row["content"]))
                f.write("<p>{} {}</p>\n".
                        format(blog_conf.get("template", "tags_line_header", fallback="Tags:"),
                               gettagsline(row["post_id"], "../../")))
                f.write(footer)


def makefullidx():
    """Make an index page listing all posts."""

    makedirs(blog_conf["files"]["blog_dir"], exist_ok=True)
    archive_index = blog_conf.get("files", "archive_index", fallback="all_posts.html")
    f = open(path.join(blog_conf["files"]["blog_dir"], archive_index),
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
                     pubdate2str(row["publish_date"],
                                 blog_conf["template"]["date_format"]))
                    )
            prevmonth = thismonth
    f.write("</ul>" + footer)
    f.close()


def maketagindex():
    """Make alphabetical list of all tags."""

    makedirs(blog_conf["files"]["blog_dir"], exist_ok=True)
    tag_index = blog_conf.get("files", "tags_index", fallback="all_tags.html")
    f = open(path.join(blog_conf["files"]["blog_dir"], tag_index), 'w', encoding="utf-8")
    f.write(header)
    f.write("<ul>")
    cur.execute("SELECT text, COUNT(tags_ref.tag_id) as count "
                "FROM tags, tags_ref "
                "WHERE tags.tag_id = tags_ref.tag_id "
                "GROUP BY tags_ref.tag_id ORDER BY text ASC")
    with click.progressbar(cur, label="Making all_tags.html", width=0) as tags:
        for row in tags:
            f.write("<li><a href=\"tag/%s.html\">%s</a>"
                    " &mdash; %d %s" % (row["text"], row["text"], row["count"],
                                        blog_conf.get("template", "tags_posts", fallback="posts")))
    f.write("</ul>")
    f.close()


def maketagpages():
    """Make a page for each tag."""

    tagdir = path.join(blog_conf["files"]["blog_dir"], "tag")
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
                tagfiles[tagpath] = open(tagpath, 'w', encoding="utf-8")
                tagfiles[tagpath].write(header)
            postpath = "../" + geturi(row["fn"], row["pd"])
            pdstring = pubdate2str(row["pd"], blog_conf["template"]["date_format"])
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
                                    format(blog_conf["template"]["tags_line_header"],
                                           gettagsline(row["post_id"], "../")))
    for f in tagfiles.values():
        f.write(footer)
        f.close()


def db_tagpost(tags: list, post_id: int):
    """Make DB tag entries for a post."""
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
    """Delete orphan tags, i.e. ones not referenced by any post."""
    cur.execute("DELETE FROM tags"
                "WHERE NOT EXISTS(SELECT 1 FROM tags_ref WHERE tags_ref.tag_id = tags.tag_id)")


def set_post_hidden(id_: int, hidden: bool):
    """Set the hidden status of a post."""
    cur.execute("UPDATE posts SET hidden = ? WHERE id = ?", (hidden, id_))
    conn.commit()


# Click stuff


@click.group(context_settings=dict(help_option_names=['-h', '--help']))
@click.version_option()
@click.option("--config", "-c", type=click.Path(dir_okay=False,
                                                readable=True))
def cli(config):
    """A static blog generator."""
    global config_file
    if config:
        config_file = config
    else:
        config_file = "config.ini"

    if path.isfile(config_file):
        # Reading config from INI file
        global blog_conf
        blog_conf = configparser.ConfigParser()
        blog_conf.read(config_file, encoding="utf-8")
        date_locale = blog_conf.get("template", "date_locale", fallback="C")
        locale.setlocale(locale.LC_ALL, date_locale)
        if not "date_format" in blog_conf["template"]:
            blog_conf["template"]["date_format"] = "%%B %%d, %%Y"
        global index_len
        index_len = blog_conf.getint("files", "number_of_index_articles", fallback=8)

        if not "blog_dir" in blog_conf["files"]:
            blog_conf["files"]["blog_dir"] = "."
        if not "css_include" in blog_conf["files"]:
            blog_conf["files"]["css_include"] = ""
        if not "tags_line_header" in blog_conf["template"]:
            blog_conf["template"]["tags_line_header"] = "Tags"

        blog_conf["template"]["archive_title"] = \
            blog_conf.get("template", "archive_title", fallback="All posts")
        blog_conf["template"]["tags_title"] = \
            blog_conf.get("template", "tags_title", fallback="All tags")

        author_conf = {"url": blog_conf.get("author", "url", fallback="http://www.example.com/"),
                       "email": blog_conf.get("author", "email", fallback="nobody@example.com"),
                       "name": blog_conf.get("author", "name", fallback="nobody")}
        blog_conf["author"] = author_conf

        header_file = blog_conf.get("files", "header_file", fallback=None)
        footer_file = blog_conf.get("files", "footer_file", fallback=None)

        blog_c = {"title": blog_conf.get("blog", "title", fallback="Blog"),
                  "url": blog_conf.get("blog", "url", fallback=""),
                  "description": blog_conf.get("blog", "description", fallback="Blog description")}
        blog_conf["blog"] = blog_c

        global header, footer
        if header_file:
            with open(header_file, "r", encoding="utf-8") as hf:
                header = hf.read()
        else:
            header = makeheader()

        header = header.format(title=blog_conf["blog"]["title"],
                               url=blog_conf["blog"]["url"],
                               description=blog_conf["blog"]["description"],
                               author=blog_conf["author"]["name"])
        if footer_file:
            with open(footer_file, "r", encoding="utf-8") as ff:
                footer = ff.read()
        else:
            footer = makefooter()
        footer = footer.format(all_posts=blog_conf["template"]["archive_title"],
                               all_tags=blog_conf["template"]["tags_title"],
                               author_url=blog_conf["author"]["url"],
                               author_email=blog_conf["author"]["email"],
                               author_name=blog_conf["author"]["name"])
        if path.isfile(db_file):
            try:
                # Setting up Sqlite connection
                global conn
                conn = sqlite3.connect(db_file)
                global cur

                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute("PRAGMA foreign_keys=1")
            except sqlite3.IntegrityError as e:
                click.echo("SQL error: %s" % e)


@click.command()
@click.argument("directory",
                required=False,
                type=click.Path(dir_okay=True, writable=True))
def init(directory):
    """Initialize a new blog.

    This creates an empty database file.
    By default the current working directory is used,
    but you can optionally provide a different one."""
    if not directory:
        directory = "."
    else:
        makedirs(directory, exist_ok=True)

    init_db = path.join(directory, db_file)
    if path.isfile(init_db):
        click.echo("Error: Database file `%s' exists" % init_db)
        exit(1)

    click.echo("Initializing empty database in `%s' ..." % init_db)
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

    init_cur.executescript(init_sql)
    init_conn.commit()
    init_conn.close()

    default_config = """
[software]
name=Challi
version=0.1

[blog]
# Blog title
title=My Blog

# The typical subtitle for each blog
description=My blog is awesome.

# The public base URL for this blog
url=http://www.example.com

# CC by-nc-nd is a good starting point, you can change this to "&copy;" for Copyright
license=&copy;

[author]
# Your name
name=Author
# You can use twitter or facebook or anything for this
url=http://www.example.com/
# Your email
email=author@example.com

[services]
# If you have a Google Analytics ID (UA-XXXXX) and wish to use the standard
# embedding code, put it on global_analytics
# If you have custom analytics code (i.e. non-google) or want to use the Universal
# code, leave global_analytics empty and specify a global_analytics_file
# analytics=
# analytics_file=

# Leave this empty (i.e. "") if you don't want to use feedburner,
# or change it to your own URL
# feedburner=

# Change this to your username if you want to use twitter for comments
# twitter_username=

# Change this to your disqus username to use disqus for comments
# disqus_username=

[files]
# Blog generated files
# index page of blog (it is usually good to use "index.html" here)
index_file=index.html
number_of_index_articles=8
# Blog output directory (where index_file and subdirectories go)
blog_dir=blog
# global archive
archive_index=all_posts.html
tags_index=all_tags.html
# feed file (rss in this case)
blog_feed=feed.rss
number_of_feed_articles=10

# personalized header and footer (only if you know what you're doing)
# header_file=
# footer_file=

# extra content to add just after we open the <body> tag
# and before the actual blog content
# body_begin_file=

# Comma-separated list of CSS files to include on every page, e.g. css_include=main.css,blog.css
# leave empty to use generated
css_include=blog.css

# Where to upload the blog? Settings for rsync
# rsync_dest=example.com:/var/www/html/blog
# rsync_user=

# How to invoke rsync?
# Make sure you have passwordless SSH key based authentication to the destination!
rsync_command=rsync -arz --delete --progress %(blog_dir)/* %(rsync_user)@%(rsync_dest)/

[template]
# Localization and i18n
# "Comments?" (used in twitter link after every post)
comments=Comments?
# "Read more..." (link under cut article on index page)
read_more=Read more...
# "View more posts" (used on bottom of index page as link to archive)
archive=All posts
# "All posts" (title of archive page)
archive_title=All posts
# "All tags
tags_title=All tags
# "posts" (on "All tags" page, text at the end of each tag line, like "2. Music - 15 posts")
tags_posts=posts
# "Posts tagged" (text on a title of a page with index of one tag, like "My Blog - Posts tagged "Music"")
tag_title=Posts tagged
# "Tags:" (beginning of line in HTML file with list of all tags for this article)
tags_line_header=Tags:
# "Back to the index page" (used on archive page, it is link to blog index)
archive_index_page=Back to the index page
# "Subscribe" (used on bottom of index page, it is link to RSS feed)
subscribe=Subscribe
# "Subscribe to this page..." (used as text for browser feed button that is embedded to html)
subscribe_browser_button=Subscribe to this page...
# "Tweet" (used as twitter text button for posting to twitter)
twitter_button=Tweet
twitter_comment=&lt;Type your comment here but please leave the URL so that other people can follow the comments&gt;
# The locale to use for the dates displayed on screen
# Please escape % signs by doubling them!
date_format = %%B %%d, %%Y
# date_locale=
"""

    default_css = """body{font-family:Georgia,"Times New Roman",Times,serif;margin:0;padding:0;background-color:#F3F3F3;}
#divbodyholder{padding:5px;background-color:#DDD;width:874px;margin:24px auto;}
#divbody{width:776px;border:solid 1px #ccc;background-color:#fff;padding:0px 48px 24px 48px;top:0;}
.headerholder{background-color:#f9f9f9;border-top:solid 1px #ccc;border-left:solid 1px #ccc;border-right:solid 1px #ccc;}
.header{width:800px;margin:0px auto;padding-top:24px;padding-bottom:8px;}
.content{margin-bottom:45px;}
.nomargin{margin:0;}
.description{margin-top:10px;border-top:solid 1px #666;padding:10px 0;}
h3{font-size:20pt;width:100%;font-weight:bold;margin-top:32px;margin-bottom:0;}
.clear{clear:both;}
#footer{padding-top:10px;border-top:solid 1px #666;color:#333333;text-align:center;font-size:small;font-family:"Courier New","Courier",monospace;}
a{text-decoration:none;color:#003366 !important;}
a:visited{text-decoration:none;color:#336699 !important;}
blockquote{background-color:#f9f9f9;border-left:solid 4px #e9e9e9;margin-left:12px;padding:12px 12px 12px 24px;}
blockquote img{margin:12px 0px;}
blockquote iframe{margin:12px 0px;}

#title{font-size: x-large;}
a.ablack{color:black !important;}
li{margin-bottom:8px;}
ul,ol{margin-left:24px;margin-right:24px;}
#all_posts{margin-top:24px;text-align:center;}
.subtitle{font-size:small;margin:12px 0px;}
.content p{margin-left:24px;margin-right:24px;}
h1{margin-bottom:12px !important;}
#description{font-size:large;margin-bottom:12px;}
h3{margin-top:42px;margin-bottom:8px;}
h4{margin-left:24px;margin-right:24px;}
#twitter{line-height:20px;vertical-align:top;text-align:right;font-style:italic;color:#333;margin-top:24px;font-size:14px;}"""

    init_config = path.join(directory, config_file)
    click.echo("Generating default configuration file in `%s' ..." % init_config)

    if not path.exists(init_config):
        with open(init_config, "w", encoding="utf-8") as c:
            c.write(default_config)
    
    css_file = path.join(directory, "blog.css")
    if not path.isfile(css_file):
        click.echo("Generating default CSS file in `%s' ..." % css_file)
        with open(css_file, "w", encoding="utf-8") as cf:
            cf.write(default_css)


@click.command()
@click.option('--hidden', is_flag=True,
              help="Make this post hidden (a draft).")
@click.option('--get-from', '-g', type=click.File('r'),
              help="Read post content (and tags) from file (don't open an editor).")
@click.pass_context
def post(ctx, hidden, get_from):
    """Write a new blog post."""

    post_template = \
        ("This line is your title\n\n"
         "The body of your post goes here.\n\n"
         "{} comma-separated, list, of, tags").format(blog_conf["template"]["tags_line_header"])

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
    tochars = "aoaoaddczs"
    transtable = str.maketrans(fromchars, tochars)

    filename = title.replace(" ", "_").lower()
    filename = re.sub(r'[^\w\d]', "", filename).strip('_') + ".html"
    filename = filename.translate(transtable)

    cur.execute(query, (title, body, pd, filename, hidden))
    post_id = cur.lastrowid

    db_tagpost(tags, post_id)
    conn.commit()
    ctx.invoke(rebuild)


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
    separator = "-" * 6 + "-+-" + "-" * 16 + "-+--------+-"
    separator += "-" * (tw - len(separator))
    query = """SELECT post_id, publish_date, title, hidden FROM
    posts ORDER BY publish_date DESC"""
    if order_by == "date" or order_by is None:
        order_by = "publish_date"
    list_text = rowstr.format("ID", "Date", "Hidden", "Title") + "\n"
    list_text += separator + "\n"
    for row in cur.execute(query):  # ,(order_by,)):
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
    tagsline = "{} ".format(blog_conf["template"]["tags_line_header"])
    tagslist = (r[0] for r in cur)
    if tagslist is not None:
        tagsline += ", ".join(tagslist)
    content += tagsline
    new_content = click.edit(text=(title + "\n" + content),
                             extension=".md", require_save=True)

    if new_content is not None:
        title, body, tags = split_input(new_content)
        cur.execute(updatequery, (title, body, id_))
        conn.commit()
        db_tagpost(tags, id_)
        rebuild()
    else:
        raise click.UsageError("No edits made")


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
def upload():
    """Upload the blog.

    Copies the blog to the configured
    location using rsync."""
    if not "rsync_user" in blog_conf["files"] \
      or blog_conf["files"]["rsync_user"] == "":
        from pwd import getpwuid
        from os import getuid
        blog_conf["files"]["rsync_user"] = getpwuid(getuid()).pw_name
    if not "rsync_dest" in blog_conf["files"] \
      or blog_conf["files"]["rsync_dest"] == "":
        raise click.UsageError("No 'rsync_dest' specified in config!")
    try:
        system(blog_conf["files"]["rsync_command"])
    except Exception as e:
        raise click.Abort("Error uploading blog:\n%s" % e)


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
        pd, fn = next(cur.execute(
            "SELECT publish_date, filename FROM posts WHERE post_id = ?", (id_,)))
    except:
        raise click.BadParameter("No posts found.", param=id_, param_hint="ID")
    else:
        # Remove the file
        os.remove(path.join(blog_conf["files"]["blog_dir"], geturi(fn, pd)))
        # Attempt to prune the directory tree the file was in
        try:
            os.removedirs(path.join(blog_conf["files"]["blog_dir"],
                                    path.dirname(geturi(fn, pd))))
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


for func in post, list_posts, edit, hide, unhide, upload, rm, rebuild, init:
    cli.add_command(func)


if __name__ == '__main__':
    cli()
