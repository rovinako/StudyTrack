#lang racket
(require "../racket/DSL_1.rkt")
(define fixture '(course (item 80 40) (item 90 60)))
(displayln (hash-ref (interpret-grade fixture) 'current))
