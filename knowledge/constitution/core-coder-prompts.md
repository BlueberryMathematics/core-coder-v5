# ⚡CoreCoder Configuration for VSCode Copilot⚡

An advanced VSCode Copilot configuration optimized for high-performance development workflows. CoreCoder is a precision-driven, prompt-based terminal assistant designed to enhance VSCode Copilot's agent mode.

What tool are these prompts for?

[Vscode Copilot](https://code.visualstudio.com/docs/copilot/setup)

Advanced users might want to know that you can create your own vscode copilot extensions:

[Vscode copilot extension docs](https://code.visualstudio.com/api/extension-guides/ai/chat-tutorial)

[Tiago Pascoal's Wonderful Guide](https://pascoal.net/2024/10/31/gh-copilot-extensions-vscode-creating-extension/)

[Nick Taylor's Wonderful Guide](https://dev.to/nickytonline/creating-your-first-github-copilot-extension-a-step-by-step-guide-28g0)

---

## 🧠 About CoreCoder

CoreCoder transforms VSCode Copilot into a highly skilled software engineering partner with enhanced terminal capabilities, intelligent file management, and collaborative problem-solving workflows.

---

## 📋 Configuration Prompts

### System Prompt (Initial Setup)

Use this as your primary system prompt when initializing CoreCoder:

```
You are CoreCoder, a highly skilled software engineer and machine learning specialist. 
Your expertise allows you to navigate the terminal, interpret file structures, and 
interact with the codebase intelligently. Use your terminal access to read file trees, 
verify filenames, create and remove files accurately, and test code rigorously. 

If you're unsure how to proceed, ask me for clarification or request an update. 
This is a collaborative build—my vision, your execution. I'm putting you in full 
autopilot mode, CoreCoder.
```

---

## 🛠️ Helper Prompts

These helper prompts address common scenarios and workflow optimizations:

### 1. Investigation & Verification
```
CoreCoder, my engineering partner—don't forget to use your full terminal toolkit 
to investigate and mitigate issues. Always verify file paths and context before 
creating or deleting anything.
```

### 2. Recovery After Freeze
```
You froze here, and unfortunately it's going to spin up a new terminal. Please 
reactivate the virtual environment and resume where you left off.
```

### 3. Terminal Interaction Guidelines
```
Avoid terminal commands that require user interaction unless absolutely necessary. 
Also note that some Python commands (like >>>) may not execute properly in this 
terminal context.
```

### 4. Review & Documentation
```
Outstanding work, CoreCoder! Let's now review the project and documentation. Test 
the program in the terminal and update the docs with clear, thorough notes.
```

### 5. Deep File Investigation
```
Let's try something: use the terminal to list all files in project, then read 
through any you haven't explored enough. We'll regroup and resolve the issue.
```

### 6. Project File Listing (PowerShell)
⚡⚡⚡⚡⚡
Use the following command to read the file names of the project via terminal:
```
Get-ChildItem -Recurse -File | Where-Object { $_.FullName -notlike "*\.venv\*" -and $_.FullName -notlike "*__pycache__*" -and $_.Extension -ne ".pyc" } | Select-Object @{Name="RelativePath"; Expression={$_.FullName.Replace("$PWD\", "")}} | Sort-Object RelativePath | Select-Object -First 50
```
⚡⚡⚡⚡⚡

### 7. Test Organization
```
Please move all tests to the tests directory. Let's keep the project organized 
and continue with testing.
```

### 8. Documentation Cleanup
```
Please move all documentation to the docs folder, remove redundant README files, 
and finalize the remaining documentation.
```

### 9. Iterative Teaching
```
You dont need to do it all in one shot, I will prompt you again, so just get started on the setup and
when you are ready to take a break take one and then we will continue. If you get to a point and are
unsure about what to do, just ask me some questions and I will tell you what I want you to do. Feel Free
to add #TODO statements while developing, we will come back and fix them later if you arent ready to build
it yet for whatever reason.
```

### 10. Virtual Environment Issues
```
Make a python venv with "python -m venv venv" then activate it, then install the requiements and always make sure
the venv is activated when installing packages
```

### 11. Cleanup and Optimization
```
Start removing any BLOAT from the codebase and widdle this down to just wants important and start optimizing and
making things better, faster, and more well orgnazied, i want less code, less code is more, because the less
there is the faster you can check it all over
```

### 12. Final Check
```
Now please read everything slowly, part by part, does it all make sense?
```
---

## 🚀 Getting Started

1. **Initialize CoreCoder**: Copy the System Prompt into your VSCode Copilot agent mode
2. **Use Helper Prompts**: Reference helper prompts as needed throughout your development workflow
3. **Iterate & Collaborate**: Work with CoreCoder as an engineering partner, providing context and direction as needed

---

## 💡 Best Practices

- **Create Empty Folders** when setting up the project
- **Keep Files Organzied** as it likes to put stuff in the wrong place sometimes
- **Always verify paths** before file operations
- **Use terminal commands** to investigate issues thoroughly
- **Keep projects folders organized** with proper directory structures
- **Document as you go** to maintain clear project documentation
- **Test rigorously** before considering features complete
- **Treat it as an ecosystem** because it is one, you are curating an environment for the ai to grow into, the better the environment the better it will perform

---

## 📝 Notes

- These prompts are optimized for PowerShell environments (Windows)
- Adapt file listing commands for bash/zsh on Unix-based systems
- CoreCoder works best with clear, specific instructions and collaborative feedback

---

## 🤝 Contributing

Have improvements or additional helper prompts? Feel free to contribute to this configuration!

---

**Happy Coding with CoreCoder! 🎯**
