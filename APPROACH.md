# How I approached this

My own running account, written as I went and left unpolished on purpose.
The measured version of all of it is in [`FINDINGS.md`](FINDINGS.md).

---

Firstly I spent time on understanding the harborframework and articles shared to understand task design, things to avoid

I started out designing task around the open source project I own which does GPU benchmarking using vllm framework, fastapi, celery, postgresql and mcp server

My first thought was a known failure we face regularly related to design around network and traffic faults: throttled registry pulls, dropped SSH channels, broker redeliveries but I realised these don't fit

Then took help from claude to design an agent that audits the leaderboard for runs which are invalid or not comparable, publishes a correct leaderboard and patches the ingest validator so the defects don't occur

oracle knows the defect classes, which runs are affected, proofs and decoys - opus 5.5 + claude code should be able to figure them out based on the nine candidate codes, seeded database, application source and mcp tools

(multi-source forensics) I took care after initial runs where claude tried to form a single script to pull just from logs or just from server API, so that it is a proper mix of all to derive all six cases

Claude solved it using psql

Then I made it harder by introducing more cases to increase difficulty

I took care to not make the task easy where claude can guess incorrect runs based on publicly available data for similar benchmark runs

Claude solved it

Tried to make it harder by introducing more defect classes

It just clicked me that even Opus 5.5 doesn't score 100% on most benchmarks (SWE-bench Pro Human Solvable 89.3%, Terminal-Bench 4.0 66.4%, SWE-bench Pro Human Difficult 50%, FrontierPhysics 27.4%), so I wanted to research on the tasks or figure out some common tasks where it scored poorly like to dig in 20-30% where it doesn't do good

I analysed SWE-bench Pro (Human Solvable), SWE-bench Pro (Human Difficult), Terminal-Bench 4.0, FrontierPhysics

Four documented agentic failure modes were

	Context exhaustion
	Premature completion
	Verification that stops short
	Broken state handoff

I designed the next set of trials with these hypotheses in mind - exceeding context deliberately, forcing it to plan under a measurement budget, making it state what it could not verify, and one built from a blind spot I had seen in its own method. I did not get to the withheld-verification and broken-handoff ones

Claude solved them all

I realised the cost of solving these tasks was very low as all the above tasks combined I had barely used $3.70

So I wanted to research on the cost and scaling aspect and wanted to understand if the tasks I was designing were really long horizon

Then I tried more defects, more gates, bigger app - they costed more but were solved but I figured out how much each unit of work was costing me and how claude was planning intelligently to effectively bring down the cost for much complex tasks

The one that actually told me something was running the same task twice and changing exactly one thing - I removed a single ambiguity from the spec and the cost dropped 42% and output tokens 54%, same container same corpus, both scored 1.000. So the expensive part was never the work, it was resolving what I had left unclear. Which is the one lever I am not allowed to pull, vague instructions and hidden requirements are disqualified by name in the brief


After all the tries my thoughts revolved around some novel ideas to figure out what is it that something humans can effectively or creatively solve that machines can't think like

I identified few research areas that can be probed like
- a person who gained insights into some area which was never formulated or can be found in papers or documented but was being solved or shown the first time to claude can make it fumble (was thinking about experts in domains and undisclosed knowledge)
- a friend of mine recently wrote a blog post about how he got to compress Sudoku to just six pixels (24 bits per RGB pixel x 6 = 144 bits) from some insights he gained after playing some extreme sudoku puzzles

For the insight #1 - I need to speak to a domain expert for specific knowledge and design a task, some of them can be really long horizon tasks like a friend of mine who is an audio ai expert working in noise suppression gained insights into how to build audio models - this task would need claude to design different models run experiments to arrive at a model that meets the specification that was cracked by a group of experts or a leaderboard that is openly being pushed every year

For the insight #2 - I think the insight my friend gained is not something that machines can easily crack but designing the task in a way its difficult for it but writing a deterministic verifier and solver is another challenge. I took help of claude to design a rubric it put claude to some real test I feel since this was an open-ended optimisation, optimum unknown but it eventually solved it

One more thing I did not expect - after I had written nine calibrators for the sudoku verifier and they all passed, I pointed a rubric evaluator at it and it found a way to score 1.000 at 14 bits while compressing nothing, by keeping state between encode and decode in the same process. I fixed it, ran it again, and the second round found my fix was incomplete because a codec can just write to /tmp. Third round came back clean. The lesson I am taking from this is my calibrators only tested the holes I had already imagined, and it took a different kind of reader to find the rest






