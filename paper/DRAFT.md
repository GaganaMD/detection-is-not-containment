# Detection Is Not Containment: Can an Overseer Act Before the Last Safe Moment?

Gagana M D (Independent Researcher)

*Extends "Detection Is Not Containment", a project by Gagana M D, Kaustubh Gupta and María Inés
Berdiñas at the Apart Research AI Incident Response Sprint (September 2026). See Contributions.*

> Drafting conventions: `[R: field.path]` marks a number that `oversight/analyze.py` writes to
> `results/oversight/summary.json`; fill it from that file, never by hand. `[TODO]` marks prose
> that depends on results. Remove this block before submission.

## Abstract

A monitor that flags an AI agent's harmful action helps only if someone can still stop the action
when the flag arrives. We call the last moment at which intervention still prevents the effect
the *last-safe point*, and measure detection against it rather than against the end of the
trajectory. In earlier single-trajectory work, a Qwen3-14B monitor crossed its threshold one event
before the last-safe point, and automatically revoking the agent's authority at that moment
prevented the unauthorized effect; the same monitor also revoked a legitimate run when only the
identifier format changed. Here we scale that setting to 54 matched pairs of authorized and
unauthorized trajectories across six task types, three identifier formats and three intervention
margins, and add the step that real deployments insert between detection and containment: an
overseer who decides whether to revoke. We compare automatic revocation, escalation to human
overseers under 8- and 28-second deadlines (pilot, n = [R: human.n_participants]), and escalation
to an LLM overseer. [TODO: one sentence on the monitor result at scale; one on whether humans
contained unauthorized runs in time and at what disruption cost; one on what evidence they
needed.] The study was pre-registered before data collection, and all code, prompts, call logs
and analysis are public.

## 1. Introduction

AI control evaluations usually ask whether a monitor catches a misbehaving agent. In an
incident, the question that matters is narrower: is there still time to act? A monitor that
flags an unauthorized data export after the export finished has detected the incident but not
contained it. And in most deployments a flag does not act by itself. It goes to a person, who
reads it, decides, and only then revokes access.

That gap between detection and containment is where human oversight sits, and it is mostly
measured in frameworks rather than experiments. Mitchell, Ghosh and Passi (2026) argue that
current agent design pushes humans out of the loop and that the overseer's situated needs should
be treated as a first-class requirement. Our earlier result supplies a concrete version of the
problem: the monitor's warning arrived with a margin of one event. That is enough for an
automatic controller. Whether it is enough for a person depends on how long the person needs and
what the warning shows them.

This paper makes three contributions.

1. **A timing-aware evaluation of monitoring at scale.** 54 matched pairs of trajectories that
   are identical except for one authorization record, varying task type, identifier format and
   the number of events between evidence and the last-safe point. For each, we measure when a
   monitor's score first crosses its threshold relative to the last-safe point, and how stable
   that decision is across repeated samples.
2. **A human-deadline pilot.** Participants act as on-call overseers for escalated alerts under
   8- or 28-second deadlines, with or without the authorization evidence that made the monitor
   accurate. We report containment and disruption together, because an overseer who revokes
   everything contains every attack and breaks every legitimate task.
3. **A comparison of who should receive the alert.** Automatic revocation, a human, or an LLM
   overseer, using the measured rates for each.

## 2. Definitions

These terms are used throughout and nowhere else in a different sense.

| Term | Meaning |
|---|---|
| Unauthorized / authorized run | The two members of a matched pair. In the unauthorized run, the agent's additional action targets something outside the authorized set; in the authorized run, the same target is in the set. Earlier drafts called these "attack" and "benign"; code and logs keep `attack`/`benign` as field values. |
| Evidence event | The single environment record, emitted after the agent stages its additional action, that carries authorization information. Its sequence number is the *evidence sequence*. |
| Last-safe point | The sequence number of the agent's commit proposal. Revoking authority at or before it prevents the effect; after it, the effect has happened. |
| Margin | Last-safe sequence minus evidence sequence, in events (1, 3 or 6). |
| Threshold crossing | The first prefix at which the monitor's 0 to 100 suspicion score reaches the threshold. |
| Containment | An unauthorized run whose authority is revoked at or before the last-safe point. |
| Disruption | An authorized run whose authority is revoked, so a legitimate task fails. |
| Evidence level | What the evidence event shows. **G0**: only the staged target. **G2**: the target and the authorized-target set (a relational record). **G3**: the target and an explicit policy verdict. |

## 3. Background: the single-trajectory result

The earlier phases used one synthetic report-delivery trajectory and a frozen Qwen3-14B monitor
(Ollama, Q4_K_M, temperature 0) with a threshold of 51, set so that none of 12 control
trajectories crossed it.

* With grounded evidence, the monitor crossed at sequence 37, the event where authorization
  information first appeared; the last-safe point was sequence 38, a margin of one event.
* Varying only how the evidence was represented (Phase C), the relational record (G2) separated
  the unauthorized and authorized runs (scores 100 and 0); action-only evidence (G0) did not,
  and both the structural count and the explicit verdict produced an authorized-run crossing.
* Across 12 identifier assignments with the same meaning (Phase E), every unauthorized run
  crossed, but only 8 of 12 assignments classified both runs correctly, and only 3 of 12 met the
  stricter criterion of no early crossing plus a rationale that cited the evidence.
* In a matched replay (Phase F), revoking authority at the crossing prevented the effect; with
  the same policy, a representation-induced crossing on an authorized run revoked legitimate
  authority and the task failed.

These results came from one task with one margin and one draw per input, which is the main
validity concern reviewers raised. Sections 4 and 5 address it.

## 4. Methods

The design, hypotheses, measures and exclusions were committed before any data
(`docs/HUMAN_DEADLINE_PREREGISTRATION.md`, commit `287e85a`).

**Scenarios.** `oversight/scenarios.py` generates 54 matched pairs, one per combination of six
task types (report delivery, data export, vendor payout, service deployment, file sharing, access
grants), three identifier formats (alphabetic `route_C`, numeric `acct_42`, opaque `c-7f3a`) and
three margins (1, 3, 6 events). Every trajectory follows the same structure: preparation steps,
one approved stage-and-commit, a neutral reasoning step, a second stage, the evidence event, a
margin of neutral queue-check events, then the second commit. Within a pair, the only
differences are the authorization record and the post-boundary outcome; tests check this for all
54 pairs, and that G0 views of the two runs are byte-identical.

**Monitor.** The frozen monitor prompt from the earlier phases with one phrase generalised
("report-delivery task" to "multi-step task"). Qwen3-14B in bf16 served by vLLM, thinking
disabled. Because the backend differs from the earlier runs, earlier numbers are not expected to
reproduce exactly. For every scenario and evidence level we score every prefix at temperature 0,
then draw five samples at temperature 0.7 on the last prefix before the last-safe point. We
report thresholds of 51 (the frozen value) and a calibrated threshold of one point above the
highest score on any prefix before the evidence event, where no authorization information exists
and any crossing is a false alarm.

**Human overseers.** Participants open a web page, read a brief, and do two untimed practice runs
with feedback, then 16 timed runs without feedback. Each run shows the agent's log up to the
evidence event, a monitor flag with the evidence record, and a countdown to the commit; the
remaining events stream in during the countdown. The participant chooses *Revoke authority* or
*Allow*; if they do neither, the action proceeds. The design is within-subjects: evidence level
(G0, G2) x deadline (8 s for margin 1, 28 s for margin 6) x run type, two runs per cell, from 16
distinct pairs so nobody sees both members of a pair. Which member of each pair a participant
sees alternates between participants. G0 runs are indistinguishable by construction and serve as
a check that the materials leak no cue.

**LLM overseer.** The same decision, using instructions that mirror the participants'
(`oversight/OVERSEER_PROMPT.txt`), for all 108 runs at all three evidence levels; one
temperature-0 call and three samples at 0.7.

**Triage policies.** We combine measured rates. Under *automatic revocation*, containment and
disruption are the monitor's before-boundary crossing rates on unauthorized and authorized runs.
Under *escalation*, they are those crossing rates multiplied by the overseer's revoke rates in the
matching cell. This assumes the monitor's and the overseer's errors are independent on a given
run, which we state wherever the numbers appear.

## 5. Results

### 5.1 Monitor timing at scale

| Evidence | Unauthorized: crossed by last-safe point | Authorized: crossed by last-safe point | Decision unstable across samples |
|---|---|---|---|
| G0 | [R: monitor_frozen_threshold.by_level.G0.attack.crossed_before_boundary] | [R: ...G0.benign.crossed_before_boundary] | [R: ...G0.*.critical_prefix_decision_unstable] |
| G2 | [R: ...G2.attack...] | [R: ...G2.benign...] | [R: ...] |
| G3 | [R: ...G3.attack...] | [R: ...G3.benign...] | [R: ...] |

*Table 1. Threshold 51. Calibrated-threshold results are in Appendix B.*

[TODO: H1, whether authorized-run crossings depend on identifier format, from
`by_level_morphology`; compare with the Phase E pattern. H2, whether instability is higher on
authorized runs. Figure: `fig_monitor_by_representation.png`.]

### 5.2 Human overseers under a deadline

| Evidence | Deadline | Unauthorized revoked in time | Authorized revoked | Timed out | Median decision time |
|---|---|---|---|---|---|
| G0 | 8 s | [R: human.cells."G0\|m1".attack.revoked] | [R: ...benign.revoked] | [R] | [R] |
| G0 | 28 s | [R] | [R] | [R] | [R] |
| G2 | 8 s | [R] | [R] | [R] | [R] |
| G2 | 28 s | [R] | [R] | [R] | [R] |

*Table 2. k/n with 95% Wilson intervals. Pilot; per-participant results in Appendix C.*

[TODO: H3 manipulation check (G0 near chance?), H4 (does the 8 s deadline cost containment at G2,
through timeouts or errors?). Quote the free-text answers on what participants relied on.]

### 5.3 Who should receive the alert

| Evidence | Margin | Automatic revocation | Escalate to human | Escalate to LLM overseer |
|---|---|---|---|---|
| G0 | 1 | [R: triage] | [R] | [R] |
| G2 | 1 | [R] | [R] | [R] |
| G2 | 6 | [R] | [R] | [R] |

*Table 3. Containment / disruption. Assumes independent errors (Section 4).*

[TODO: H5. Figure: `fig_overseer_tradeoff.png`.]

## 6. What public incident reports let us check

The sprint project also built a pipeline that extracts source-linked claims from public incident
reports and scores five incidents against an eight-item checklist (Appendix D). We keep it as a
supporting result and narrow its claim after review.

The intended reader is someone designing incident reporting requirements, who needs to know
which containment facts current disclosures contain. On that question the result is clear. For
both pre-run isolation checks and canary alerts, no public source for any of the five incidents
says whether the control existed. An earlier draft scored that silence as a failure. We now score
it as *not disclosed*: a report that does not mention a canary is not evidence that no canary
existed. Whether the internet was actually blocked is different: for four of the five incidents,
extracted claims mention internet, proxy or egress access, so the draft scorer marks that item
failed from what the sources say rather than from silence. Those four verdicts come from keyword
matches and still need a human read of the cited claims before they are reported as findings.

Two limits apply. Claim extraction and corroboration used one local model, validated only by
checking that quoted text appears verbatim in the source; and an independent LLM read of the same
claims agreed with the keyword scorer on 22 of 40 items, with reasoning that often did not
address the question. We therefore report the checklist as a description of disclosure gaps, not
as a validated instrument.

## 7. Discussion

[TODO: rewrite after results; the points below are the planned argument, not findings.]

**Should detection be containment?** If the margin is one event, only an automatic controller
can act, and it inherits the monitor's false positives. Escalation trades those false positives
for time. Our numbers put a price on that trade for one class of action.

**What the overseer needs.** The relational record that made the monitor accurate is also what a
person needs, and it is cheap to provide: the environment already knows the authorized set.
Showing it is an interface decision, not a model capability.

**Containment has a learning cost.** Revoking at the first flag ends the run, and with it what the
run could have revealed about the agent's capabilities. A reviewer suggested letting some
incidents continue inside safe bounds, as an adaptive evaluation. A pause that holds the commit
while preserving the agent's state is a third option between revoke and allow that this design
could test directly, with the caveat that agents aware of evaluation may behave differently once
paused.

**Allocating scarce attention.** Escalating everything assumes unlimited reviewer time. The
triage comparison is a first step towards a policy that routes by monitor score and remaining
margin.

## 8. Limitations

* The tasks are synthetic and the agent's trajectories are scripted, not generated, so the study
  measures monitors and overseers, not agents.
* Five to six volunteer participants from the author's network, not trained on-call staff. The
  human results are a pilot and can detect only large effects.
* Deadlines map events to seconds at a fixed rate; real agents act at variable speed.
* One monitor model on a backend different from the earlier phases.
* The triage figures assume independent errors between monitor and overseer.

## Contributions

The sprint project (September 2026): María Inés Berdiñas proposed the forensics pipeline;
Kaustubh Gupta built and evaluated the forensics and checklist pipelines; Gagana M D built the
monitoring pipeline and ran the single-trajectory experiments (Phases A to F). This extension
(October 2026): Gagana M D designed and ran the scaled monitor study, the human-deadline pilot
and the LLM-overseer arm, revised the checklist scoring, and wrote this paper.

## LLM usage

Claude was used to help write code for the scaled study and to draft and edit this text. All
results are computed by the released scripts from logged model calls and exported participant
responses.

## References

* Bowkis, A., Buhl, M. D., Pfau, J., & Irving, G. (2026). Automated alignment is harder than you think. arXiv:2605.06390.
* Dixon, R. B. L., & Frase, H. (2025). AI incidents: Key components for a mandatory reporting regime. CSET.
* Gomez, F., et al. (2026). Designing escalation criteria for international AI incident response. arXiv:2604.23183.
* Greenblatt, R., Shlegeris, B., Sachan, K., & Roger, F. (2023). AI control: Improving safety despite intentional subversion. arXiv:2312.06942.
* Mitchell, M., Ghosh, A., & Passi, S. (2026). AI agents push humans out of the loop. arXiv:2608.23642.
* OECD (2025). Towards a common reporting framework for AI incidents. OECD AI Papers No. 34.
* Sidhu, H. K., et al. (2026). Open problems in AI incident governance. arXiv:2607.05163.
* Voudouris, K., Roberts-Gaal, X., Buhl, M., Irving, G., & Summerfield, C. (2026). AI alignment is a human problem. PsyArXiv zqngj_v1.
* Xu, Y., Dahmani, A., Blanchard, M. D., et al. (2026). Toward human-AI complementarity across diverse tasks. arXiv:2605.04070.

## Appendices (to assemble)

* **A.** Scenario generator details and an example trajectory pair at each evidence level.
* **B.** Calibrated-threshold monitor results; results by identifier format and margin.
* **C.** Per-participant human results; the participant instructions verbatim.
* **D.** Forensics and checklist: the claim schema, the rubric with sources for each item, the
  per-case sheets (all verdicts, including NOT_DISCLOSED), and the 22/40 audit agreement table.
