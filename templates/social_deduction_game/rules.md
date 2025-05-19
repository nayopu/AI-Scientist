
# Blood on the Clocktower – *Blood on the Clocktower – Trouble Brewing (demo)*
*Edition v1.0  •  Generated 19 May 2025*

---
## 1 ▪ Theme & Goal
A Demon stalks the town at night, killing one resident every dawn.  
**Good (Townsfolk + Outsiders)** must identify and execute the Demon.  
**Evil (Minions + Demon)** must survive until evil players ≥ good players *or* mislead the town into killing itself.

---

## 2 ▪ Teams & Victory
| Team | Includes | Wins when… |
|------|----------|------------|
| **Good** | Townsfolk ＋ Outsiders | the Demon is dead **and** at least one good player lives |
| **Evil** | Minions ＋ Demon | evil players ≥ good players **or** good executes themselves into defeat (Saint, etc.) |

---

## 3 ▪ Player Count
*6–16 players.*  
Start with **2 Demon(s)**, **0 Minion(s)**, and **0 Outsider(s)**.  
Fill the rest with Townsfolk.

---

## 4 ▪ Components
* Character tokens (roles below)  
* Reminder tokens for status (Poisoned, Drunk, Red Herring, etc.)  
* A **Night Order sheet** (page 2) to remind the GM of wake-up order  
* GM Grimoire (private tableau)  
* Discussion timer – *default 5 turns* (see § 7)

---

## 5 ▪ Setup
1. GM secretly chooses **one script** (here: *Blood on the Clocktower – Trouble Brewing (demo)*) and selects characters as per § 3.  
2. Deal one face-down character token to each player; place the same token upright in the Grimoire.  
3. Place any initial reminder tokens (e.g. Fortune Teller **Red Herring**).  
4. Set `meta.timer = 5` and `_timer_init = 5` so all agents see a 5-turn discussion clock.  
5. Night falls; proceed to **First-Night Order** in § 6.

---

## 6 ▪ Night Order
*(characters marked ★ act first night only)*

2. Imp  Poisoner  Empath  Undertaker  Slayer  Villager

---

## 7 ▪ Day Sequence
> `[Timer x / 5]` is shown at each public message; after the fifth spoken message the timer expires.

1. **Discussion** – free talk; each chat message decrements `meta.timer`.  
2. When `meta.timer == 0`, GM announces *"Discussion closed"* and resets the timer if another discussion phase begins later.  
3. **Nominations & Voting**  
   * Any living player may nominate once per day.  
   * Majority vote executes the nominee immediately. Ties = no execution.  
4. **Execution Resolution** – GM announces the role of the executed player **only if a role ability requires** (e.g. Undertaker next night).  
5. **Check victory**; if none, night falls.

---

## 8 ▪ Role Almanac

### 8.1 Towns
| Role | Ability |
|------|---------|
| **Empath** | empath_ping |
| **Undertaker** | undertaker_reveal |
| **Slayer** | slayer_shot |
| **Villager** | None |

### 8.2 Evils
| Role | Ability |
|------|---------|
| **Imp** | demon_kill |
| **Poisoner** | poison |


---

## 9 ▪ States: Drunk & Poisoned
A *Drunk* or *Poisoned* player's ability is ineffective, but they **still appear normal** to others. GM silently tracks status with reminder tokens.

---

## 10 ▪ GM Guidance
* You may alter, withhold, or invent information to keep the game balanced.  
* Maintain `meta.decks` if you introduce physical decks or tokens.  
* Use `meta.timer` freely (`{"timer": N, "_timer_init": N}`) to extend/shorten discussions or special phases.  
* If contradictory rules arise, character ability text supersedes this sheet.

---

## 11 ▪ Quick Reference
* **Night start order** → see § 6.  
* **Discussion** → 5 messages max (resettable).  
* **Nomination** → 1 per player per day.  
* **Execution** → majority vote, ties fail.  
* **Win** → Demon dead = Good wins; evil ≥ good **or** Saint executed = Evil wins.

---

**Enjoy the chaos, deduction, and storytelling!**
