BEGIN TRANSACTION;
-- Relation table: tag <-> post
CREATE TABLE `tags_ref` (
	`tag_ref_id`	INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE,
	`tag_id`	INTEGER NOT NULL,
	`post_id`	INTEGER NOT NULL,
	FOREIGN KEY(`tag_id`) REFERENCES tags("tag_id"),
	FOREIGN KEY(`post_id`) REFERENCES posts("post_id")
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
	FOREIGN KEY(`post_id`) REFERENCES posts("post_id")
);
CREATE INDEX `post_pub_date` ON `posts` (`publish_date` DESC);
CREATE INDEX `author_name` ON `authors` (`name` ASC);
COMMIT;
