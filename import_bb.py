#!/usr/bin/env python3

import sqlite3
import os
from datetime import datetime

bb_dir = 'bb'
pybb = 'pybb.db'

# Open database connection
conn = sqlite3.connect(pybb)
cur = conn.cursor()
cur.execute("PRAGMA foreign_keys=1")

# Walk Bashblog directory
for top, dirs, files in os.walk(bb_dir):
  for name in files:
    # Look for Markdown files
    if os.path.splitext(name)[1] in (".md", ".MD", "*.markdown"):
      # Get each file's last modified timestamp
      mtime = os.stat(os.path.join(top, name)).st_mtime
      pybb_post_date = datetime.utcfromtimestamp(mtime)
      # Get each filename without extension
      pybb_post_filename = os.path.splitext(name)[0] + ".html"
      # Open each file read-only
      with open(os.path.join(top, name), 'r', encoding="utf-8") as f:
        pybb_post_content = ""
        for i, line in enumerate(f):
          # The first line always contains the post title with no markup
          if i == 0:
            pybb_post_title = line.strip()
          # There is one line specially prefixed containing a comma separated
          # list of tags.
          elif line.startswith( "Luokat: " ):
            pybb_post_tags = line.strip().replace("Luokat: ", "", 1).split(", ")
          # All other lines are collected as the post body.
          else:
            pybb_post_content += line
      # Insert the post
      cur.execute("""INSERT INTO `posts` (title, content, publish_date, filename)
                  VALUES (?, ?, ?, ?)""",
                  (pybb_post_title, pybb_post_content, pybb_post_date, pybb_post_filename)
                  )
      # Take note of what autoincremented id we got
      post_id = cur.lastrowid

      for tag in pybb_post_tags:
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
