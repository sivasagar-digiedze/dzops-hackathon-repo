import re

def extract_questions(output):
    questions = []

    for line in output.split("\n"):
        raw = line.strip()

        if not raw:
            continue

        if "answer:" in raw.lower():
            continue

        if raw.endswith("?"):
            clean = re.sub(r"[-:*]*\s*", "", raw)

            if not any(x in clean.lower() for x in ["priority", "service", "cloud"]):
                questions.append(clean)

    return list(dict.fromkeys(questions))