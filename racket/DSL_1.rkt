#lang racket
;; Grade & Progress DSL. Syntax: (course (item score-or-#f weight-percent) ...)
;; #f means ungraded, not zero. No eval and no mutable accumulator.
(provide interpret-grade)
(require racket/match)
(define (finite-number? n) (and (real? n) (not (nan? n)) (not (infinite? n))))
(define (parse-item form)
  (match form
    [(list 'item score weight)
     (unless (and (finite-number? weight) (< 0 weight) (<= weight 100))
       (error 'grade "weight must be greater than 0 and at most 100"))
     (unless (or (eq? score #f) (and (finite-number? score) (<= 0 score 100)))
       (error 'grade "score must be 0–100 or #f"))
     (cons score weight)]
    [_ (error 'grade "expected (item score weight)" )]))
(define (interpret-grade program)
  (match program
    [(list 'course forms ...)
     (define items (map parse-item forms))
     (define total (apply + (map cdr items)))
     (when (> total (+ 100 0.000001)) (error 'grade "weights exceed 100"))
     (define graded (filter (lambda (x) (not (eq? (car x) #f))) items))
     (define weight (apply + (map cdr graded)))
     (define earned (apply + (map (lambda (x) (/ (* (car x) (cdr x)) 100)) graded)))
     (hash 'current (if (zero? weight) 'null (exact->inexact (/ (* earned 100) weight)))
           'earned (exact->inexact earned) 'graded_weight (exact->inexact weight)
           'configured_weight (exact->inexact total))]
    [_ (error 'grade "expected (course (item ...) ...)" )]))
(module+ main (displayln (interpret-grade '(course (item 80 40) (item 90 60)))))
(module+ test
  (require rackunit)
  (check-equal? (hash-ref (interpret-grade '(course (item 80 40) (item 90 60))) 'current) 86.0)
  (check-equal? (hash-ref (interpret-grade '(course (item 0 40) (item #f 60))) 'current) 0.0)
  (check-equal? (hash-ref (interpret-grade '(course)) 'current) 'null)
  (check-exn exn:fail? (lambda () (interpret-grade '(course (item 101 40)))))
  (check-exn exn:fail? (lambda () (interpret-grade '(course (item 80 70) (item 90 60)))))
  (check-exn exn:fail? (lambda () (interpret-grade '(system "anything"))))
  (check-exn exn:fail? (lambda () (interpret-grade '(course (item +nan.0 40)))))
  (check-exn exn:fail? (lambda () (interpret-grade '(course (item 90 0))))))
