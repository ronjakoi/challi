#!/usr/bin/env python3

import sqlite3
import os
from datetime import datetime

outdir = 'blog'
bb_dir = 'bb'
db_file = 'challi.db'

# Open database connection
conn = sqlite3.connect(db_file)
cur = conn.cursor()
cur.execute("PRAGMA foreign_keys=1")

os.makedirs(outdir, exist_ok=True)
htaccess = open(os.path.join(outdir, ".htaccess"), 'a')
# Walk Bashblog directory
for top, dirs, files in os.walk(bb_dir):
  for name in files:
    # Look for Markdown files
    if os.path.splitext(name)[1] in (".md", ".MD", "*.markdown"):
      # Get each file's last modified timestamp
      mtime = os.stat(os.path.join(top, name)).st_mtime
      post_date = datetime.utcfromtimestamp(mtime). \
                       strftime("%Y-%m-%d %H:%M:%S")
      # Get each filename without extension
      post_filename = os.path.splitext(name)[0] + ".html"
      # Open each file read-only
      with open(os.path.join(top, name), 'r', encoding="utf-8") as f:
        post_content = ""
        for i, line in enumerate(f):
          # The first line always contains the post title with no markup
          if i == 0:
            post_title = line.strip()
          # There is one line specially prefixed containing a comma separated
          # list of tags.
          elif line.startswith( "Luokat: " ):
            post_tags = line.strip().replace("Luokat: ", "", 1).split(", ")
          # All other lines are collected as the post body.
          else:
            post_content += line
      # Insert the post
      cur.execute("""INSERT INTO `posts` (title, content, publish_date, filename, hidden)
                  VALUES (?, ?, ?, ?, ?)""",
                  (post_title, post_content, post_date, post_filename, False)
                  )
      post_path_new = '{}/{:02d}/{}'.format(post_date[0:4],
                                    int(post_date[5:7]),
                                    post_filename)
      htaccess.write("Redirect /{} /{}\n".format(post_filename, post_path_new))
      # Take note of what autoincremented id we got
      post_id = cur.lastrowid

      for tag in post_tags:
        # Check if a tag with this text already exists
        cur.execute("SELECT tag_id FROM tags WHERE text = ?", (tag,))
        try:
          tag_id = cur.fetchone()[0]
        # If not, insert it
        except TypeError: # fetchone() returns None if no more rows
          cur.execute("INSERT INTO tags (text) VALUES (?)", (tag,))
          tag_id = cur.lastrowid
        # Insert a relation tag <-> post
        cur.execute("INSERT INTO tags_ref (tag_id, post_id) VALUES (?, ?)",
                    (tag_id, post_id))
      # Commit the transaction (all posts, all tags)
      conn.commit()
conn.close()
htaccess.close()