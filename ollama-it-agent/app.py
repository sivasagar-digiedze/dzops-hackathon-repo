from tools.llm_tool import llm_tool
from tools.question_tool import extract_questions
from tools.command_tool import extract_commands, run_commands


def process_ticket(ticket, step=0):
    MAX_STEPS = 3

    prompt = f"""
You are a STRICT IT SUPPORT AGENT.

RULES:
- DO NOT guess
- Ask questions if needed

Ticket: {ticket}
Step: {step}
"""

    output = llm_tool(prompt)

    questions = extract_questions(output)

    has_solution = (
        "Issue:" in output and
        "Solution:" in output and
        "Commands:" in output
    )

    # Ask questions
    if questions and not has_solution and step < MAX_STEPS:
        return {
            "status": "need_info",
            "questions": questions,
            "step": step
        }

    # Final answer
    final_output = llm_tool("Give final answer:\n" + ticket)

    commands = extract_commands(final_output)

    command_results = run_commands(commands)

    return {
        "status": "resolved",
        "result": final_output,
        "commands": command_results
    }   