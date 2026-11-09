"""Declarative paradigm: parameterized SQL declares relationships and filtering."""

import sqlite3
from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS courses (
 id INTEGER PRIMARY KEY, title TEXT NOT NULL UNIQUE,
 target REAL NOT NULL CHECK(target BETWEEN 0 AND 100));
CREATE TABLE IF NOT EXISTS assignments (
 id INTEGER PRIMARY KEY, course_id INTEGER NOT NULL REFERENCES courses(id),
 title TEXT NOT NULL, due TEXT NOT NULL,
 weight REAL NOT NULL CHECK(weight > 0 AND weight <= 100),
 minutes INTEGER NOT NULL CHECK(minutes BETWEEN 1 AND 1440),
 score REAL CHECK(score BETWEEN 0 AND 100),
 completed INTEGER NOT NULL DEFAULT 0 CHECK(completed IN (0,1)));
CREATE TABLE IF NOT EXISTS plans (
 id INTEGER PRIMARY KEY, created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 content TEXT NOT NULL, mode TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS lectures (
 id INTEGER PRIMARY KEY, course_id INTEGER NOT NULL REFERENCES courses(id),
 title TEXT NOT NULL, filename TEXT NOT NULL, sections_json TEXT NOT NULL,
 characters INTEGER NOT NULL, created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS lectures_course ON lectures(course_id);
CREATE TABLE IF NOT EXISTS study_guides (
 id INTEGER PRIMARY KEY, course_id INTEGER NOT NULL REFERENCES courses(id),
 content_json TEXT NOT NULL, reviewed_text TEXT,
 created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS guides_course ON study_guides(course_id);
"""

UPCOMING_SQL = """
SELECT a.*, c.title AS course
FROM assignments a
JOIN courses c ON c.id = a.course_id
WHERE a.completed = 0 AND a.due BETWEEN ? AND ?
ORDER BY a.due, a.id
"""


def db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"], timeout=10)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db


def close_db(_error=None):
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def rows(sql, params=()):
    return [dict(row) for row in db().execute(sql, params).fetchall()]


def due_tasks(today, end):
    return rows(UPCOMING_SQL, (today, end))


def open_tasks():
    return rows("""SELECT a.*, c.title AS course FROM assignments a
        JOIN courses c ON c.id=a.course_id WHERE a.completed=0 ORDER BY a.due,a.id""")
