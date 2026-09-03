# CS-RL-101 — Week 1

## MDPs and the Bellman Equation

Introduces Markov decision processes, derives the Bellman optimality equation from their four ingredients, and turns it into the value iteration algorithm. A board-work detour on a dice game motivates solving the last decision first.

**Objectives**

- Name the four ingredients of an MDP and the role of the discount factor.
- Write the Bellman optimality equation and explain why it is recursive.
- Run one sweep of value iteration by hand and state its stopping rule.

### Markov decision processes

[0:01–2:29 · slide 1]

Sequential decision making starts with a Markov decision process. An MDP is fully specified by four ingredients; the Bellman equation later in the lecture is nothing more than these four written down recursively.

- States $s \in S$ — everything the agent needs to know right now
- Actions $a \in A$ — the choices available in each state
- Reward $R(s, a)$ — a number received for taking $a$ in $s$
  - Immediate and given; not to be confused with value
- Transition function $T(s, a, s')$ — where you land after each action
- Discount factor $\gamma \in [0, 1)$ — how much later rewards count
  - $\gamma \to 0$: myopic, only the next reward counts
  - $\gamma \to 1$: far-sighted, but sums may diverge

**Markov property** — The next state depends only on the current state and action, not on the history that led there.

> **PITFALL** — Reward vs value: the reward is the number you get right now; the value is the total discounted reward you expect from here on. Students mix these up every year.

### Board work: the reroll game

[2:31–4:28]

Away from the slides: roll a fair six-sided die and receive the face value in dollars. The game is worth its expected payout, 3.5, so paying anything less is a bargain.

Now allow one reroll. The trick is to value the second roll first, because its worth is already known: keep the first roll only if it beats 3.5, i.e. a 4, 5 or 6.

$$
\mathbb{E}[\text{reroll game}] = \tfrac{1}{2}\cdot\tfrac{4+5+6}{3} + \tfrac{1}{2}\cdot 3.5 = 4.25
$$

> **ASIDE** — This is dynamic programming in miniature: solve the last decision first, then use its value to make the earlier one. The same idea drives value iteration.

### The Bellman equation

[4:31–6:59 · slide 2]

The value of a state is the immediate reward plus gamma times the expected value of wherever you land next. The equation is recursive: the value on the left shows up again on the right-hand side.

$$
V(s) = \max_a \Big[ R(s, a) + \gamma \sum_{s'} T(s, a, s')\, V(s') \Big]
$$

| Term | Meaning |
| --- | --- |
| $V(s)$ | value of state $s$ |
| $\max_a$ | best action available |
| $\sum_{s'} T(s, a, s')$ | expectation over next states |
| $\gamma$ | discount factor |

> **EXAM** — Write the Bellman equation down properly, with the max over actions and the sum over next states. This will be on the exam.

> Once you believe the Bellman equation has a unique fixed point, everything else in this lecture follows.
> — Lecturer, on the principle of optimality

### Value iteration

[7:01–9:05 · slide 3]

Value iteration turns the equation into an update rule: start with every value at zero and sweep over all the states, applying the update once per state.

```python
def value_iteration(mdp, gamma, eps):
    V = {s: 0.0 for s in mdp.states}
    while True:
        delta = 0.0
        for s in mdp.states:
            best = max(
                mdp.R(s, a)
                + gamma * sum(p * V[s2] for s2, p in mdp.T(s, a))
                for a in mdp.actions(s)
            )
            delta = max(delta, abs(best - V[s]))
            V[s] = best
        if delta < eps:
            return V
```

![Line plot of maximum value change per sweep, decaying geometrically](assets/fig-value-iteration-convergence.png)
*Maximum change between successive sweeps on a small grid world; it falls geometrically with rate gamma.*

When the biggest change falls below the tolerance epsilon, stop and read off the greedy policy by picking the best action in every state.

> **UNCERTAIN** — The lecturer said the error 'shrinks by a factor of gamma every time'. That is the contraction bound; the observed per-sweep ratio can be smaller.

### Glossary

- **Discount factor** — $\gamma \in [0, 1)$; weights a reward $k$ steps ahead by $\gamma^k$.
- **Value function** — $V(s)$: the expected total discounted reward starting from state $s$ and acting optimally.
- **Greedy policy** — The policy that picks, in every state, the action maximising the Bellman bracket.

### Open questions

- Why does the Bellman equation have exactly one fixed point for gamma < 1?
- How many sweeps does value iteration need to reach a given epsilon?

## Policies and Policy Iteration

Defines policies, derives the Bellman expectation equation for a fixed policy, and introduces policy iteration as an alternative to value iteration.

**Objectives**

- Define a policy and the state-value function under a policy.
- Explain the two steps of policy iteration and when it terminates.

### Policies and the state-value function

[0:00–3:00 · slide 1]

A policy $\pi$ maps states to actions. Fixing a policy turns the MDP into a Markov chain with rewards, and the value of a state under that policy satisfies a linear version of last lecture's equation.

$$
V^{\pi}(s) = R(s, \pi(s)) + \gamma \sum_{s'} T(s, \pi(s), s')\, V^{\pi}(s')
$$

- No max: the action is chosen by $\pi$, so the system is linear
- Can be solved exactly by matrix inversion for small state spaces

### Policy iteration

[3:00–7:00 · slides 2–3]

Policy iteration alternates two steps until the policy stops changing: evaluate the current policy, then improve it greedily.

| Step | What it does | Cost |
| --- | --- | --- |
| Evaluate | Solve $V^{\pi}$ for the current $\pi$ | One linear solve |
| Improve | Set $\pi(s) \leftarrow \arg\max_a [\cdot]$ | One sweep |

> **EXAM** — Be able to compare policy iteration with value iteration: few expensive iterations versus many cheap ones.

### Glossary

- **Policy** — A mapping $\pi: S \to A$ from states to actions.

### Open questions

- Does policy iteration always terminate in finitely many steps?
