#lang racket
(require json "DSL_1.rkt" "DSL_2.rkt")
(define data (read-json))
(define result
  (cond
    [(equal? (hash-ref data 'operation) "grade")
     (interpret-grade
      `(course ,@(map (lambda (x) `(item ,(if (eq? (hash-ref x 'score) 'null) #f (hash-ref x 'score))
                                       ,(hash-ref x 'weight))) (hash-ref data 'items))))]
    [(equal? (hash-ref data 'operation) "plan")
     (interpret-plan
      `(study-plan (available ,(hash-ref data 'available))
                   ,@(map (lambda (x) `(task ,(hash-ref x 'id) ,(hash-ref x 'minutes)))
                          (hash-ref data 'tasks))))]
    [else (error 'runner "unknown operation")]))
(write-json result)
