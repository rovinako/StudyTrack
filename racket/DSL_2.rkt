#lang racket
;; Smart Study Assistant DSL. Allocates minutes in the supplied priority order.
;; Syntax: (study-plan (available 120) (task 1 60) (task 2 90))
(provide interpret-plan)
(require racket/match)
(define (parse-task form)
  (match form
    [(list 'task id duration)
     (unless (and (exact-positive-integer? id) (exact-positive-integer? duration) (<= duration 1440))
       (error 'plan "task id and minutes must be positive integers, minutes at most 1440"))
     (cons id duration)]
    [_ (error 'plan "expected (task id minutes)" )]))
(define (allocate tasks left)
  (cond [(or (empty? tasks) (zero? left)) (hash 'sessions '() 'unused_minutes left)]
        [else
         (define duration (min left (cdar tasks)))
         (define rest (allocate (cdr tasks) (- left duration)))
         (hash 'sessions (cons (hash 'id (caar tasks) 'minutes duration) (hash-ref rest 'sessions))
               'unused_minutes (hash-ref rest 'unused_minutes))]))
(define (interpret-plan program)
  (match program
    [(list 'study-plan (list 'available minutes) forms ...)
     (unless (and (exact-nonnegative-integer? minutes) (<= minutes 1440))
       (error 'plan "available must be a whole number from 0 to 1440"))
     (define tasks (map parse-task forms))
     (unless (= (length tasks) (length (remove-duplicates (map car tasks))))
       (error 'plan "duplicate task id"))
     (allocate tasks minutes)]
    [_ (error 'plan "expected (study-plan (available minutes) (task ...) ...)" )]))
(module+ main (displayln (interpret-plan '(study-plan (available 120) (task 1 60) (task 2 90)))))
(module+ test
  (require rackunit)
  (define result (interpret-plan '(study-plan (available 120) (task 1 60) (task 2 90))))
  (check-equal? (map (lambda (x) (hash-ref x 'minutes)) (hash-ref result 'sessions)) '(60 60))
  (check-equal? (hash-ref result 'unused_minutes) 0)
  (check-equal? (hash-ref (interpret-plan '(study-plan (available 0) (task 1 60))) 'sessions) '())
  (check-equal? (hash-ref (interpret-plan '(study-plan (available 120))) 'unused_minutes) 120)
  (check-exn exn:fail? (lambda () (interpret-plan '(study-plan (available -1)))))
  (check-exn exn:fail? (lambda () (interpret-plan '(study-plan (available 10) (task 1 0)))))
  (check-exn exn:fail? (lambda () (interpret-plan '(study-plan (available 10) (task 1 5) (task 1 5)))))
  (check-exn exn:fail? (lambda () (interpret-plan '(unknown)))))
