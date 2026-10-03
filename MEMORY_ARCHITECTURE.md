# Customer memory architecture

Status: proposed. Needs sign-off on the decisions at the end before code changes.

## 1. What is broken today

Verified by running three real agent turns on a scratch tenant (not just read from code):

| # | Problem | Evidence | Impact |
|---|---|---|---|
| 1 | **History is duplicated on every turn.** | After 3 customer messages the stored thread had 7 customer messages and 3 system prompts. "probe message 1" appeared 4 times. | The agent re-reads its own history each turn. Token cost and latency grow with every message, and the context fills with repeats. |
| 2 | **Summaries are silently dropped.** | The summarizer failed on the same run with a pydantic `list_type` error. Its output is parsed straight into `ConversationSummary` with no coercion or retry. | The long-term summary never gets saved, so long conversations lose their earlier context. The failure is logged as a warning and nothing else happens. |
| 3 | **The agent is blind to the restaurant's replies.** (from reading the code) | Owner replies are saved to `messages` by `persist_outbound`, but the LangGraph checkpoint is only written by the agent. | After a handback the agent answers without knowing what the owner already promised, e.g. a refund or an ETA. |

Root cause of 1: `run_customer_support_turn` builds `exec_messages` from the recent history and the system prompt, then passes them to `ainvoke`. The checkpointer is keyed by thread, so LangGraph appends them to the stored messages each turn. `clean_history` is computed and then never used.

## 2. Principles

1. **One source of truth for what was said:** the `messages` collection. Every inbound, agent, and staff message is already stored there with a timestamp and sender. Memory is built from it, not from a second copy inside LangGraph.
2. **The agent run is stateless between turns.** Each turn builds its input from the stored data. Tool-call state lives only inside one invocation, so the LangGraph checkpointer is not needed for chat history.
3. **Derived facts are computed, not incremented.** Order counts and spend come from `orders`. A counter that is `$inc`'d can drift, and it is what makes `total_orders` unreliable today.
4. **Failures are visible.** A failed summary is retried once, then recorded with an error state. It is never silently dropped.
5. **Tenant isolation everywhere.** Every memory key is `(tenant_id, customer_phone)`, and every query is scoped by `tenant_id`.

## 3. Layers

| Layer | Stored in | Contents | When it is updated |
|---|---|---|---|
| **Working window** | `messages` (read directly) | The last K messages of the conversation, in time order. Customer messages are `user`. Agent and staff messages are `assistant`, and staff messages are prefixed `[restaurant staff]`. | Read each turn. |
| **Rolling summary** | `conversation_summaries`, one current doc per conversation | Summary of everything older than the window, plus `covers_until` (the timestamp of the last message it covers) | When messages older than the window exceed a threshold |
| **Customer profile** | `customer_profiles` (structured facts) plus `orders` (derived stats) | Name, delivery addresses, dietary notes, favourite items. Order count and spend are computed from `orders`. | Facts: after a turn that changes them, with a source message ID. Stats: computed on read. |

Each turn the prompt is assembled as:

```
[system: restaurant config + policies]
[system: customer profile facts + order stats]
[system: rolling summary, if any]
[last K messages from the window, with staff messages marked]
[current customer message]
```

## 4. Changes, in order

1. **Stop replaying history into the checkpointer.** Build the input from the layers above and run the agent without a persisted thread. This fixes problem 1 directly and removes the duplicated system prompts.
2. **Make the summariser reliable.** Input is the messages since the last watermark, not the whole thread. Output is parsed with coercion (a string where a list is expected becomes a one-item list, for example). One retry on a parse failure. On a second failure, store `status: "failed"` with the error, so it can be seen and retried.
3. **Show staff replies to the agent.** Staff messages are part of the window, so after a handback the agent has them in context.
4. **Derive customer stats from `orders`.** Remove the `$inc` counters. The "VIP / Frequent" tier and total spend read the orders collection (excluding `pending` and `cancelled`, the same rule as revenue).
5. **Profile facts with provenance.** Facts extracted from a conversation are stored with the message ID they came from. The owner can see and correct them later (Phase 5 "Menu knowledge / Settings" area).

## 5. Indexes

- `messages`: `{conversation_id: 1, created_at: 1}` (window reads)
- `conversation_summaries`: `{conversation_id: 1}` unique, one current summary per conversation, with `covers_until`
- `orders`: `{tenant_id: 1, customer_phone: 1, created_at: -1}` (customer stats and history)

## 6. Migration

- The existing `langgraph_checkpoints*` collections are left in place and stop being written. Nothing reads them after step 1.
- Existing summaries are not migrated. They are regenerated from `messages` on the first turn after the change.
- Customer profile counters are replaced by queries. The old fields can be left until nothing reads them.

## 7. Open questions (need your decision)

1. **Approve dropping the LangGraph checkpointer for chat history?** This is the change that fixes duplication. The alternative is keeping it and only fixing the replay, which leaves the staff-reply blind spot in place.
2. **Window size K.** Proposed: the last 12 messages, capped by a token budget of about 1,500 tokens. Larger costs more per turn.
3. **How much the agent sees of staff replies.** Full text, or only a note such as "a staff member replied about a refund"? Full text is more accurate. The note protects private details.
4. **Retention.** How long customer messages are kept. Nothing expires today. A TTL is easy to add, but it should be decided before real customers are onboarded.
