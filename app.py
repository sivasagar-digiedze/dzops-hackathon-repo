import ollama
import os
import re
import subprocess

# 🔧 Ensure correct connection
os.environ["OLLAMA_HOST"] = "http://127.0.0.1:11434"


# 🔍 Extract ONLY valid questions
def extract_questions(output):
    questions = []

    for line in output.split("\n"):
        raw = line.strip()

        if not raw:
            continue

        # ❌ Ignore model self answers
        if "answer:" in raw.lower():
            continue

        # ✅ Only proper questions
        if raw.endswith("?"):
            clean = re.sub(r"[-:*]*\s*", "", raw)

            if not any(x in clean.lower() for x in ["priority", "service", "cloud"]):
                questions.append(clean)

    # ✅ remove duplicates but keep order
    seen = set()
    final = []
    for q in questions:
        if q not in seen:
            final.append(q)
            seen.add(q)

    return final


# 🌐 Cloud VM Disk Check (SSH)
def check_disk_space_cloud():
    print("\n🌐 Cloud VM detected. Enter access details:\n")

    vm_ip = input("Enter VM IP: ")
    username = input("Enter username (e.g., ubuntu/ec2-user): ")
    key_path = input("Enter path to SSH key (.pem): ")

    print("\n🔍 Checking disk space on cloud VM...\n")

    try:
        cmd = f"ssh -i {key_path} {username}@{vm_ip} df -h"

        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True
        )

        if result.stderr:
            print("⚠️ Error:\n", result.stderr)

        print("📊 Disk Usage:\n")
        print(result.stdout)

        return result.stdout

    except Exception as e:
        print("❌ Error connecting to VM:", e)
        return None


# ⚙️ Run local commands (if not cloud)
def run_commands(output):
    commands = []
    capture = False

    for line in output.split("\n"):
        line = line.strip()

        if line.lower().startswith("commands"):
            capture = True
            continue

        if capture:
            if not line or ":" in line:
                break

            line = line.replace("*", "").strip()
            commands.append(line)

    if not commands:
        return

    print("\n⚙️ Executing commands locally:\n")

    for cmd in commands:
        print(f"> {cmd}")
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True
            )
            print(result.stdout)
        except Exception as e:
            print("Error:", e)


# 🤖 Main function
def process_ticket(ticket, step=0):

    MAX_STEPS = 3

    prompt = f"""
You are a STRICT IT SUPPORT AGENT.

CRITICAL RULES:
- DO NOT assume anything
- DO NOT guess cloud/provider
- If info is missing → ASK QUESTIONS
- Ask MAX 2 questions
- Ask in plain sentences (no headings)
- DO NOT give solution if unsure

IMPORTANT:
- If cloud is not mentioned → Cloud: UNKNOWN
- If service unclear → Service: UNKNOWN

FINAL ANSWER ONLY WHEN READY:

Priority:
Service:
Cloud:

Issue:
Root Cause:
Solution:
Commands:

Ticket:
{ticket}

Step: {step}
"""

    try:
        response = ollama.chat(
            model='llama3',
            messages=[{'role': 'user', 'content': prompt}]
        )

        output = response['message']['content'].strip()

    except Exception as e:
        print("\n❌ Error:", e)
        return

    # 🔍 Extract questions
    questions = extract_questions(output)

    # ✅ Check if final answer exists
    has_solution = (
        "Issue:" in output and
        "Solution:" in output and
        "Commands:" in output
    )

    # 🚨 BLOCK HALLUCINATED CLOUD
    if "Cloud:" in output:
        cloud_line = [l for l in output.split("\n") if "Cloud:" in l]

        if cloud_line:
            cloud_value = cloud_line[0].lower()

            if any(x in cloud_value for x in ["aws", "azure", "gcp"]):
                if "unknown" not in cloud_value and step < MAX_STEPS:
                    has_solution = False
                    questions = ["Which environment is this (AWS, Azure, GCP, or On-Prem)?"]

    # 🔥 Detect cloud disk issue EARLY
    is_disk_issue = "disk" in ticket.lower()
    is_cloud = any(x in ticket.lower() for x in ["cloud", "aws", "azure", "gcp"])

    if is_disk_issue and is_cloud:
        cloud_output = check_disk_space_cloud()

        if cloud_output:
            print("\n🧠 LLM Analysis based on real data:\n")

            analysis_prompt = f"""
Analyze this disk usage output:

{cloud_output}

Give:
- Usage status
- Severity
- Possible cause
- What to clean
- Fix recommendation
"""

            response = ollama.chat(
                model='llama3',
                messages=[{'role': 'user', 'content': analysis_prompt}]
            )

            print(response['message']['content'])
            return

    # 👉 Ask questions
    if questions and not has_solution and step < MAX_STEPS:
        for q in questions:
            ans = input(q + " ")
            ticket += " " + ans

        return process_ticket(ticket, step + 1)

    # 🔥 Force final answer
    if step >= MAX_STEPS or not questions:
        final_prompt = f"""
You are an IT support expert.

STRICT:
- Do NOT guess
- If unknown → write UNKNOWN

Give FINAL answer:

Priority:
Service:
Cloud:

Issue:
Root Cause:
Solution:
Commands:

Ticket:
{ticket}
"""

        response = ollama.chat(
            model='llama3',
            messages=[{'role': 'user', 'content': final_prompt}]
        )

        final_output = response['message']['content'].strip()

        print("\n" + final_output + "\n")

        run_commands(final_output)
        return

    # ✅ If model gives solution early
    if has_solution:
        print("\n" + output + "\n")
        run_commands(output)
        return


# 🚀 Start
if __name__ == "__main__":
    ticket = input("Enter ticket: ")
    process_ticket(ticket)