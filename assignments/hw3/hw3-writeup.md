# SEIS 606 HW3: Task, Plan, and Implement
## Reflections & Next Iteration
This process was quite interesting, as I had never made use of slash commands in Copilot before, nor had I tried the specify toolkit until now. I was impressed with how seamless and painless the process was.

I'm concerned at the speed at which AI works compared to the speed at which I understand what its doing. It feels easy to get carried away without fully understanding each step, and I'm guilty of it here. I'm using AI in a novel way compared to how I normally apply it to work and personal projects. Generally, I have a deeper understanding of what's going on every step of the process, but there's an overwhelming amount of TODOs and documentation to review here. The best analogy I can think of is studying for a test — this feels like I'm getting all the answers, but I won't be prepared for any curveballs if the test were to ask about the specifics of this app. I'll build my understanding with time, of course.

To keep token usage low(er), I let Copilot decide which models to route my requests to. I remember seeing GPT-6 mentioned, though it was definitely one of the smaller variants of it. It wasn't until the implement step where I deliberately chose a powerful model (`MAI-Code-1.1-Flash`), to ensure good results.

Overall, this took me about an hour to complete. I spent some time overthinking how to best install `specify-cli`, managing my development environment, and getting distracted. But the commands worked smoothly and I made sure to monitor them as they went so it didn't feel so "hands off". I noted the commands I ran below — they're in the same order I executed them.

## Project Setup
I first created a new directory for project files...

```bash
mkdir project
cd project
specify init --here --ai copilot
```

And then I copied content from HW2 into this new directory. The plan is to keep the homework folders for instructions / iterative deliverables, and then work out of the root-level `project/` directory going forward.

## Constitution
```bash
/speckit-constitution
```


## Specify
```bash
/speckit-specify
```


## Clarify
```bash
/speckit-clarify
```
This step took about 15 minutes. I forgot to note which model specifically performed this task.

## Plan
```bash
/speckit-plan
```


## Tasks
```bash
/speckit-tasks
```


## Implement
```bash
/speckit-implement
```

This step, run by `MAI-Code-1.1-Flash` via Copilot, took 5 minutes and 13 seconds.


## Converge
```bash
/speckit-converge
```

This step took the second longest amount of time (4m10s). Though it was optional, it helped further refine the project.
