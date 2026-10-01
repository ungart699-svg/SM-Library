-- Run this in phpMyAdmin's Import tab (with smart_library selected)
-- Adds more books per genre so content-based recommendations
-- have something to actually suggest once you borrow one book.

INSERT INTO books (title, author, genre, description, isbn, total_copies, available_copies) VALUES
-- More Fantasy
('The Name of the Wind', 'Patrick Rothfuss', 'Fantasy', 'A gifted young man grows into a legendary figure while recounting his own extraordinary life story.', '9780756404741', 2, 2),
('Mistborn: The Final Empire', 'Brandon Sanderson', 'Fantasy', 'A crew of thieves plots to overthrow an immortal tyrant in a world blanketed by ash.', '9780765311788', 2, 2),
('A Game of Thrones', 'George R.R. Martin', 'Fantasy', 'Noble families vie for control of an iron throne while an ancient threat stirs in the north.', '9780553103540', 3, 3),

-- More Science Fiction
('Foundation', 'Isaac Asimov', 'Science Fiction', 'A mathematician predicts the fall of a galactic empire and works to preserve civilization through it.', '9780553293357', 2, 2),
('Ender''s Game', 'Orson Scott Card', 'Science Fiction', 'A brilliant child is trained to lead humanity''s defense against an alien invasion.', '9780812550702', 3, 3),
('The Martian', 'Andy Weir', 'Science Fiction', 'An astronaut stranded on Mars must use ingenuity and science to survive until rescue.', '9780553418026', 2, 2),

-- More Romance
('Emma', 'Jane Austen', 'Romance', 'A well-meaning but meddlesome young woman navigates love and matchmaking in her small town.', '9780141439587', 3, 3),
('Jane Eyre', 'Charlotte Bronte', 'Romance', 'An orphaned governess finds love and independence despite a mysterious secret in her employer''s past.', '9780141441146', 3, 3),
('Outlander', 'Diana Gabaldon', 'Romance', 'A World War II nurse is swept back in time to 18th century Scotland and falls in love.', '9780440212560', 2, 2),

-- More Technology
('The Pragmatic Programmer', 'David Thomas', 'Technology', 'Practical advice and philosophy for becoming a more effective, adaptable software developer.', '9780135957059', 2, 2),
('Design Patterns', 'Erich Gamma', 'Technology', 'A catalog of reusable solutions to common problems in object-oriented software design.', '9780201633610', 2, 2),
('You Don''t Know JS', 'Kyle Simpson', 'Technology', 'A deep dive into the parts of JavaScript most developers misunderstand or avoid.', '9781491924464', 2, 2),

-- More Non-fiction
('Educated', 'Tara Westover', 'Non-fiction', 'A woman raised in a strict survivalist family fights for an education that transforms her life.', '9780399590504', 3, 3),
('Atomic Habits', 'James Clear', 'Non-fiction', 'A practical framework for building good habits and breaking bad ones through small changes.', '9780735211292', 3, 3),
('Thinking, Fast and Slow', 'Daniel Kahneman', 'Non-fiction', 'A Nobel laureate explores the two systems that drive the way people think and make decisions.', '9780374533557', 2, 2);
