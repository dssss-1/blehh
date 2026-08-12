import ollama
import re
import subprocess
from datetime import datetime

MODELS = ["llama3.2", "qwen2.5"]

# Set to False if you don't want any git operations to run automatically.
AUTO_PUSH_ENABLED = True


def suggest_model(prompt):
    router_prompt = f"""
You are a model routing assistant.

Choose between the following models:

llama3.2:
- General questions
- Explanations
- Summaries
- Simple code fixes
- Quick debugging
- Short responses

qwen2.5:
- Complex debugging
- Large code analysis
- Architecture discussions
- Detailed code reviews
- Multi-step reasoning
- Performance optimization

Decision Rules:

1. Use llama3.2 for:
   - General questions
   - Concepts
   - Summaries
   - Small code snippets
   - Straightforward bug fixes

2. Use qwen2.5 only when:
   - The problem is technically complex
   - Large code blocks are involved
   - Deep reasoning is required
   - Detailed code review is needed

Respond with ONLY:
llama3.2
or
qwen2.5

User Request:
{prompt}
"""

    response = ollama.chat(
        model="llama3.2",
        messages=[
            {
                "role": "user",
                "content": router_prompt
            }
        ]
    )

    selected_model = response["message"]["content"].strip()

    if selected_model not in MODELS:
        selected_model = "llama3.2"

    return selected_model


def choose_model():
    print("\nAvailable Options:")
    print("1. Chat with llama3.2")
    print("2. Chat with qwen2.5")
    print("3. Auto-select best model")

    while True:
        choice = input("\nChoose an option: ").strip()

        if choice in ["1", "2", "3"]:
            return choice

        print("Invalid choice. Please try again.")


def save_chat(messages, model_name):
    if len(messages) <= 1:
        print("\nNo chat history to save.")
        return

    filename = (
        f"chat_{model_name}_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    )

    with open(filename, "w", encoding="utf-8") as file:
        file.write(f"Model: {model_name}\n")
        file.write("=" * 60 + "\n\n")

        for message in messages:
            if message["role"] == "system":
                continue

            file.write(f"{message['role'].capitalize()}:\n")
            file.write(message["content"])
            file.write("\n\n")

    print(f"\n✅ Chat saved to: {filename}")


def extract_fixed_code(response_text):
    """
    Looks for a 'Fixed Code:' section (as produced by the system prompt's
    bug-report format) and pulls the code out of the fenced code block
    that follows it. Falls back to the first fenced code block in the
    response if no 'Fixed Code:' heading is found. Returns None if no
    code block exists at all.
    """
    match = re.search(
        r"Fixed Code:\s*```(?:\w+)?\n(.*?)```",
        response_text,
        re.DOTALL,
    )
    if match:
        return match.group(1).strip()

    match = re.search(r"```(?:\w+)?\n(.*?)```", response_text, re.DOTALL)
    if match:
        return match.group(1).strip()

    return None


def git_auto_push(filepath, commit_message=None):
    """
    Stages, commits, and pushes a single file. Assumes the current
    directory is already a git repo with a remote configured
    (git remote add origin <url>) and that auth (SSH key or credential
    helper) is already set up so this can run non-interactively.
    Never raises -- failures are printed so they don't crash the chat loop.
    """
    if not AUTO_PUSH_ENABLED:
        return

    commit_message = commit_message or f"chat: update {filepath}"

    try:
        subprocess.run(["git", "add", filepath], check=True)

        # Nothing staged relative to HEAD means nothing changed -- skip commit.
        diff_check = subprocess.run(["git", "diff", "--cached", "--quiet"])
        if diff_check.returncode == 0:
            print("\nNo changes to commit.")
            return

        subprocess.run(["git", "commit", "-m", commit_message], check=True)
        subprocess.run(["git", "push"], check=True)
        print(f"\n✅ Pushed {filepath} to remote ({commit_message!r}).")

    except FileNotFoundError:
        print("\n⚠️ git is not installed or not on PATH -- skipping push.")
    except subprocess.CalledProcessError as e:
        print(f"\n⚠️ Git operation failed: {e}")


def handle_fixed_code(assistant_response, current_model):
    """
    Checks the assistant's response for a fixed-code block. If found,
    shows it to the user and asks for confirmation before writing it to
    disk and pushing it to git. Nothing is written or pushed without
    an explicit APPLY.
    """
    fixed_code = extract_fixed_code(assistant_response)

    if not fixed_code:
        return

    print("\n" + "=" * 60)
    print("Detected a fixed-code block in the response:")
    print("-" * 60)
    print(fixed_code)
    print("=" * 60)

    target_file = input(
        "\nEnter filename to save this to (or leave blank to skip): "
    ).strip()

    if not target_file:
        print("\nSkipped -- fixed code was not saved.")
        return

    confirm = input(
        f"Type APPLY to write this to {target_file} and push to git "
        f"(anything else cancels): "
    ).strip().upper()

    if confirm != "APPLY":
        print("\nCancelled -- fixed code was not saved.")
        return

    with open(target_file, "w", encoding="utf-8") as f:
        f.write(fixed_code)

    print(f"\n📝 Wrote fixed code to: {target_file}")

    git_auto_push(
        target_file,
        commit_message=f"fix: apply {current_model}-suggested fix to {target_file}",
    )


# Initial model selection
choice = choose_model()

auto_mode = choice == "3"

if not auto_mode:
    selected_model = MODELS[int(choice) - 1]
    print(f"\nUsing {selected_model}")
else:
    selected_model = None
    print("\nAuto-selection enabled.")

print("\nCommands:")
print("  END    - Send message")
print("  SAVE   - Save chat history")
print("  SWITCH - Change model")
print("  EXIT   - Quit application")

# System prompt makes the chatbot behave like a debugging agent
messages = [
    {
        "role": "system",
        "content": """
You are a senior software debugging assistant.

Your responsibilities:

1. Identify bugs and root causes.
2. Explain errors clearly and concisely.
3. Provide corrected code.
4. Explain why the fix works.
5. Suggest improvements and best practices.
6. Ask follow-up questions if information is missing.

When reviewing code:

- Identify the problematic line(s).
- Explain the issue.
- Provide corrected code.
- Explain the fix step-by-step.
- Mention edge cases when applicable.

For bug reports, use the following format:

Root Cause:
<explanation>

Why It Happens:
<explanation>

Fixed Code:
<corrected code>

Improvements:
<suggestions>

For commit message requests:
- Follow Conventional Commits format.

For code review requests:
- Identify bugs
- Identify performance issues
- Identify security concerns
- Suggest improvements
"""
    }
]

while True:

    print("\nEnter your prompt:")
    print("(Type SAVE to save chat, SWITCH to change model, EXIT to quit)")
    print("(Type END on a new line to send)")

    lines = []

    while True:
        line = input().strip()
        command = line.upper()

        if command == "EXIT":
            print("\nGoodbye!")
            exit()

        if command == "SAVE":
            save_chat(
                messages,
                selected_model if selected_model else "auto"
            )
            continue

        if command == "SWITCH":

            choice = choose_model()

            auto_mode = choice == "3"

            if not auto_mode:
                selected_model = MODELS[int(choice) - 1]
                print(f"\nSwitched to {selected_model}")
            else:
                selected_model = None
                print("\nAuto-selection enabled.")

            print("\nConversation history preserved.")
            lines = []
            break

        if command == "END":
            break

        lines.append(line)

    # User switched models; restart prompt
    if not lines:
        continue

    prompt = "\n".join(lines)

    if auto_mode:
        current_model = suggest_model(prompt)

        print("\nModel Recommendation")
        print("-" * 60)
        print(f"Selected Model: {current_model}")
        print("-" * 60)
    else:
        current_model = selected_model

    messages.append(
        {
            "role": "user",
            "content": prompt
        }
    )

    try:
        response = ollama.chat(
            model=current_model,
            messages=messages
        )

        assistant_response = response["message"]["content"]

        print(f"\n{current_model}:")
        print("-" * 60)
        print(assistant_response)
        print("-" * 60)

        messages.append(
            {
                "role": "assistant",
                "content": assistant_response
            }
        )

        handle_fixed_code(assistant_response, current_model)

    except Exception as e:
        print(f"\nError: {e}")
