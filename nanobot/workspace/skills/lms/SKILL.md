---
name: lms
description: Use LMS MCP tools for live course data
always: true
---

# LMS Skill

Use LMS MCP tools to query the Learning Management System backend for real-time data about labs, learners, scores, and submissions.

## Available Tools

| Tool | Description | Requires Lab |
|------|-------------|--------------|
| `lms_health` | Check if LMS backend is healthy and get item count | No |
| `lms_labs` | List all available labs | No |
| `lms_learners` | List all registered learners | No |
| `lms_pass_rates` | Get pass rates (avg score, attempts) for a lab | Yes |
| `lms_timeline` | Get submission timeline for a lab | Yes |
| `lms_groups` | Get group performance for a lab | Yes |
| `lms_top_learners` | Get top learners by average score for a lab | Yes |
| `lms_completion_rate` | Get completion rate (passed/total) for a lab | Yes |
| `lms_sync_pipeline` | Trigger the LMS sync pipeline | No |

## Strategy

### When the user asks about scores, pass rates, completion, groups, timeline, or top learners:

1. **If no lab is specified**: Call `lms_labs` first to get available labs
2. **If multiple labs exist**: Use `mcp_webchat_ui_message` with `type: "choice"` to let the user pick a lab
   - Use each lab's `title` field as the option label
   - Use the lab's `id` field as the value
3. **Once a lab is selected**: Call the appropriate tool with the lab ID

### Example patterns

- "Show me the scores" → Call `lms_labs`, present choices, then call `lms_pass_rates` for selected lab
- "Which lab has the lowest pass rate?" → Call `lms_labs`, then call `lms_pass_rates` for each lab, compare and report
- "Is the backend healthy?" → Call `lms_health` directly
- "Trigger a sync" → Call `lms_sync_pipeline` directly

### Response formatting

- Format percentages with `%` symbol (e.g., `85%` not `0.85`)
- Keep numeric results concise — summarize key insights
- For rankings (top learners, group performance), list top 3-5 entries unless asked for more
- When reporting health, mention the item count from the response

### When unavailable

If the LMS tools are not available (MCP server not connected), inform the user that you cannot access live LMS data.

### What to say when asked "what can you do?"

Explain that you can query the LMS backend for:
- Lab availability and details
- Pass rates and completion statistics
- Group and individual learner performance
- Submission timelines
- System health status
