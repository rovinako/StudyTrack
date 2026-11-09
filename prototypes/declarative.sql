-- Run in isolation: sqlite3 :memory: < prototypes/declarative.sql
CREATE TABLE tasks(id INTEGER PRIMARY KEY,title TEXT,due TEXT,completed INTEGER);
INSERT INTO tasks VALUES (1,'A','2026-04-20',0),(2,'B','2026-04-21',1),(3,'C','2026-04-30',0);
SELECT title FROM tasks WHERE completed=0 AND due BETWEEN '2026-04-18' AND '2026-04-25' ORDER BY due,id;
-- Expected: A
