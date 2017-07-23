#!/usr/bin/env python3

import sqlite3
import os
from datetime import datetime

bb_dir = 'bb'
pybb = 'pybb.db'

conn = sqlite3.connect(pybb)

for top, dirs, files in os.walk(bb_dir):
  for name in files:
    if os.path.splitext(name)[1] == ".md":
      mtime = os.stat(os.path.join(top, name)).st_mtime
      pybb_post_date = datetime.utcfromtimestamp(mtime)
      pybb_post_filename = os.path.splitext(name)[0]
      with open(os.path.join(top, name), 'r', encoding="utf-8") as f:
        pybb_post_content = ""
        for i, line in enumerate(f):
          if i == 0:
            pybb_post_title = line.strip()
          elif not line.startswith("Luokat: "):
            pybb_post_content += line
          
      print("Post: ", pybb_post_filename, "\nModified: ",
            datetime.isoformat(pybb_post_date),
            "\nContent: ", pybb_post_content, "\n----")
      

conn.close()
