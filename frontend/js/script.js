    const chatContainer = document.getElementById("chatContainer");
    const messageInput = document.getElementById("messageInput");
    const sendBtn = document.getElementById("sendBtn");
    const statusText = document.getElementById("status");
    const conversationList = document.getElementById("conversationList");
    const modelSelect = document.getElementById("modelSelect");
    const noticeText = document.getElementById("noticeText");
    const micBtn = document.getElementById("micBtn");

    let threadId = localStorage.getItem("thread_id");

    if (!threadId) {
        threadId = crypto.randomUUID();
        localStorage.setItem("thread_id", threadId);
    }

    const savedModel = localStorage.getItem("selected_model");

    if (savedModel && modelSelect) {
        const availableModels = Array.from(modelSelect.options).map(
            option => option.value
        );

        if (availableModels.includes(savedModel)) {
            modelSelect.value = savedModel;
        }
    }

    if (modelSelect) {
        modelSelect.addEventListener("change", () => {
            localStorage.setItem("selected_model", modelSelect.value);

            if (noticeText) {
                noticeText.textContent = `Selected model: ${modelSelect.value}`;
            }
        });
    }

    let recognition = null;
    let isDictating = false;

    function setupSpeechRecognition() {
        const SpeechRecognition =
            window.SpeechRecognition || window.webkitSpeechRecognition;

        if (!SpeechRecognition) {
            return null;
        }

        const speechRecognition = new SpeechRecognition();

        speechRecognition.lang = "en-US";
        speechRecognition.continuous = true;
        speechRecognition.interimResults = true;

        speechRecognition.onstart = () => {
            isDictating = true;

            if (micBtn) {
                micBtn.classList.add("recording");
                micBtn.textContent = "⏹️";
            }

            statusText.textContent = "Listening...";
        };

        speechRecognition.onresult = (event) => {
            let finalTranscript = "";
            let interimTranscript = "";

            for (let i = event.resultIndex; i < event.results.length; i++) {
                const transcript = event.results[i][0].transcript;

                if (event.results[i].isFinal) {
                    finalTranscript += transcript + " ";
                } else {
                    interimTranscript += transcript;
                }
            }

            if (finalTranscript) {
                const currentText = messageInput.value.trim();

                messageInput.value = currentText
                    ? currentText + " " + finalTranscript.trim()
                    : finalTranscript.trim();

                autoResize(messageInput);
            }

            if (interimTranscript && noticeText) {
                noticeText.textContent = "Listening: " + interimTranscript;
            }
        };

        speechRecognition.onerror = (event) => {
            console.error("Speech recognition error:", event.error);

            if (event.error === "not-allowed") {
                alert("Microphone permission denied. Please allow microphone access.");
            }

            stopDictation();
        };

        speechRecognition.onend = () => {
            if (isDictating) {
                try {
                    speechRecognition.start();
                } catch (error) {
                    stopDictation();
                }
            }
        };

        return speechRecognition;
    }

    function toggleDictation() {
        if (!recognition) {
            recognition = setupSpeechRecognition();
        }

        if (!recognition) {
            alert("Speech recognition is not supported in this browser. Please use Chrome or Edge.");
            return;
        }

        if (isDictating) {
            stopDictation();
        } else {
            startDictation();
        }
    }

    function startDictation() {
        try {
            recognition.start();
        } catch (error) {
            console.error("Could not start dictation:", error);
        }
    }

    function stopDictation() {
        isDictating = false;

        if (recognition) {
            try {
                recognition.stop();
            } catch (error) {
                console.error("Could not stop dictation:", error);
            }
        }

        if (micBtn) {
            micBtn.classList.remove("recording");
            micBtn.textContent = "🎙️";
        }

        statusText.textContent = "Ready";

        if (noticeText) {
            noticeText.textContent = "DevGPT can make mistakes. Check important info.";
        }

        messageInput.focus();
    }

    function autoResize(textarea) {
        textarea.style.height = "auto";
        textarea.style.height = textarea.scrollHeight + "px";
    }

    function hideWelcome() {
        const welcome = document.getElementById("welcome");
        const cards = document.getElementById("cards");

        if (welcome) welcome.style.display = "none";
        if (cards) cards.style.display = "none";
    }

    function handleKeyDown(event) {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            sendMessage();
        }
    }

    function usePrompt(text) {
        messageInput.value = text;
        autoResize(messageInput);
        messageInput.focus();
    }

    function openFilePicker() {
        document.getElementById("fileInput").click();
    }

    function addMessage(role, content = "") {
        hideWelcome();

        const messageDiv = document.createElement("div");
        messageDiv.className = role === "user"
            ? "message user"
            : "message assistant";

        const avatar = document.createElement("div");
        avatar.className = role === "user"
            ? "avatar user-avatar"
            : "avatar bot-avatar";

        avatar.textContent = role === "user" ? "U" : "AI";

        const messageContent = document.createElement("div");
        messageContent.className = "message-content";
        messageContent.textContent = content;

        messageDiv.appendChild(avatar);
        messageDiv.appendChild(messageContent);

        chatContainer.appendChild(messageDiv);
        chatContainer.scrollTop = chatContainer.scrollHeight;

        return messageContent;
    }

    function detectLikelyTool(message) {
        const text = message.toLowerCase();

        const mathPattern = /(\d+\s*[\+\-\*\/]\s*\d+)|calculate|calculation|math|solve/;
        const ragPattern = /document|pdf|file|uploaded|summarize|summary|according to|based on/;
        const memorySavePattern = /remember that|save this|store this|keep in memory|memorize/;
        const memoryRecallPattern = /what do you remember|recall|my memory|remember about me/;

        const webSearchPattern =
            /latest|current|today|now|recent|news|search web|web search|internet|online|price|version|update|2025|2026|who is|what is happening|trending|release|new model|current ceo|latest version/;

        if (memorySavePattern.test(text)) {
            return "Memory Save";
        }

        if (memoryRecallPattern.test(text)) {
            return "Memory Recall";
        }

        if (ragPattern.test(text)) {
            return "Document Search";
        }

        if (webSearchPattern.test(text)) {
            return "Web Search";
        }

        if (mathPattern.test(text)) {
            return "Calculator";
        }

        return null;
    }

    function addToolProgress(toolName) {
        const wrapper = document.createElement("div");
        wrapper.className = "tool-progress";

        const box = document.createElement("div");
        box.className = "tool-progress-box";

        const icon = document.createElement("span");
        icon.className = "tool-spinner";

        const text = document.createElement("span");
        text.textContent = `Using ${toolName}...`;

        box.appendChild(icon);
        box.appendChild(text);
        wrapper.appendChild(box);

        chatContainer.appendChild(wrapper);
        chatContainer.scrollTop = chatContainer.scrollHeight;

        return {
            wrapper,
            icon,
            text
        };
    }

    function completeToolProgress(toolProgress, toolName) {
        if (!toolProgress) return;

        toolProgress.icon.className = "tool-check";
        toolProgress.icon.textContent = "✓";
        toolProgress.text.textContent = `${toolName} completed`;
    }

    async function loadConversations() {
        try {
            const response = await fetch("/conversations");
            const data = await response.json();

            conversationList.innerHTML = "";

            if (!data.conversations || data.conversations.length === 0) {
                conversationList.innerHTML = `
                    <div class="history-item">No chats yet</div>
                `;
                return;
            }

            data.conversations.forEach(conv => {
                const item = document.createElement("div");
                item.className = "history-item";

                if (conv.thread_id === threadId) {
                    item.classList.add("active");
                }

                item.textContent = conv.title || "New Chat";
                item.onclick = () => loadConversation(conv.thread_id);

                conversationList.appendChild(item);
            });

        } catch (error) {
            console.error("Failed to load conversations:", error);
        }
    }

    async function loadConversation(selectedThreadId) {
        threadId = selectedThreadId;
        localStorage.setItem("thread_id", threadId);

        try {
            const response = await fetch(`/history/${threadId}`);
            const data = await response.json();

            chatContainer.innerHTML = "";

            if (!data.messages || data.messages.length === 0) {
                renderWelcome();
                await loadConversations();
                return;
            }

            data.messages.forEach(msg => {
                addMessage(
                    msg.role === "user" ? "user" : "assistant",
                    msg.content
                );
            });

            await loadConversations();

        } catch (error) {
            console.error("Failed to load conversation:", error);
        }
    }

    function renderWelcome() {
        chatContainer.innerHTML = `
            <div class="welcome" id="welcome">
                <h1>How can I help you today?</h1>
                <p>Ask questions, upload documents, use tools, search the web, and chat with memory.</p>
            </div>

            <div class="cards" id="cards">
                <div class="card" onclick="usePrompt('Search the web for latest AI agent news.')">
                    Search latest web info
                </div>

                <div class="card" onclick="usePrompt('Summarize the document I uploaded.')">
                    Summarize uploaded document
                </div>

                <div class="card" onclick="usePrompt">
                    Save something to memory
                </div>

                <div class="card" onclick="usePrompt('Calculate 125 * 48 / 6')">
                    Use calculator tool
                </div>
            </div>
        `;
    }

    function parseSSEPart(part) {
        const lines = part
            .split(/\r?\n/)
            .filter(line => line.trim().startsWith("data:"));

        if (lines.length === 0) {
            return null;
        }

        const jsonText = lines
            .map(line => line.replace(/^data:\s*/, ""))
            .join("\n")
            .trim();

        if (!jsonText || jsonText === "[DONE]") {
            return null;
        }

        try {
            return JSON.parse(jsonText);
        } catch (error) {
            console.error("Invalid stream JSON:", jsonText, error);
            return null;
        }
    }

    async function sendMessage() {
        const message = messageInput.value.trim();

        if (!message) return;

        if (isDictating) {
            stopDictation();
        }

        const selectedModel = modelSelect ? modelSelect.value : "openai/gpt-oss-120b";

        addMessage("user", message);

        messageInput.value = "";
        messageInput.style.height = "auto";

        sendBtn.disabled = true;
        statusText.textContent = `Thinking with ${selectedModel}...`;

        const likelyTool = detectLikelyTool(message);
        let toolProgress = null;

        if (likelyTool) {
            toolProgress = addToolProgress(likelyTool);
            statusText.textContent = `Using ${likelyTool}...`;
        }

        const botElement = addMessage("assistant", "");

        let firstTokenReceived = false;

        function handleStreamData(data) {
            if (!data) return;

            if (data.token !== undefined && data.token !== null) {
                if (!firstTokenReceived) {
                    firstTokenReceived = true;

                    if (likelyTool && toolProgress) {
                        completeToolProgress(toolProgress, likelyTool);
                    }

                    statusText.textContent = `Generating with ${selectedModel}...`;
                }

                botElement.textContent += data.token;
                chatContainer.scrollTop = chatContainer.scrollHeight;
            }

            if (data.error) {
                if (likelyTool && toolProgress) {
                    completeToolProgress(toolProgress, likelyTool);
                }

                botElement.textContent += "\n\nError: " + data.error;
                statusText.textContent = "Ready";
                chatContainer.scrollTop = chatContainer.scrollHeight;
            }

            if (data.done) {
                if (likelyTool && toolProgress && !firstTokenReceived) {
                    completeToolProgress(toolProgress, likelyTool);
                }

                statusText.textContent = "Ready";
            }
        }

        try {
            const response = await fetch("/chat/stream", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    message: message,
                    thread_id: threadId,
                    model: selectedModel
                })
            });

            if (!response.ok) {
                let errorText = "Request failed.";

                try {
                    const errorData = await response.json();
                    errorText = errorData.detail || errorData.message || errorText;
                } catch (error) {
                    console.error("Could not parse error response:", error);
                }

                botElement.textContent = errorText;
                return;
            }

            if (!response.body) {
                botElement.textContent = "Streaming is not supported by this browser.";
                return;
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder("utf-8");

            let buffer = "";

            while (true) {
                const { value, done } = await reader.read();

                if (done) {
                    break;
                }

                buffer += decoder.decode(value, { stream: true });

                const parts = buffer.split(/\r?\n\r?\n/);
                buffer = parts.pop() || "";

                for (const part of parts) {
                    const data = parseSSEPart(part);
                    handleStreamData(data);
                }
            }

            /*
                Important fix:
                Sometimes the final streamed response does not end with "\n\n".
                In that case, the final data remains inside buffer.
                This part makes sure the leftover buffer is also displayed.
            */
            buffer += decoder.decode();

            if (buffer.trim()) {
                const data = parseSSEPart(buffer);
                handleStreamData(data);
            }

        } catch (error) {
            console.error("Streaming error:", error);

            if (likelyTool && toolProgress) {
                completeToolProgress(toolProgress, likelyTool);
            }

            botElement.textContent = "Something went wrong: " + error.message;

        } finally {
            sendBtn.disabled = false;
            statusText.textContent = "Ready";
            messageInput.focus();

            await loadConversations();
        }
    }

    async function uploadFile() {
        const fileInput = document.getElementById("fileInput");

        if (!fileInput.files.length) {
            return;
        }

        const file = fileInput.files[0];

        addMessage("user", `📎 Uploaded document: ${file.name}`);

        const toolProgress = addToolProgress("Document Ingestion");
        statusText.textContent = "Using Document Ingestion...";

        const formData = new FormData();
        formData.append("file", file);
        formData.append("thread_id", threadId);

        try {
            const response = await fetch("/upload", {
                method: "POST",
                body: formData
            });

            const data = await response.json();

            completeToolProgress(toolProgress, "Document Ingestion");

            if (data.success) {
                addMessage(
                    "assistant",
                    data.message + "\n\nYou can now ask questions about this document."
                );

                await loadConversations();
            } else {
                addMessage("assistant", "Upload failed: " + data.message);
            }

        } catch (error) {
            completeToolProgress(toolProgress, "Document Ingestion");
            addMessage("assistant", "Upload failed: " + error.message);
        }

        statusText.textContent = "Ready";
        fileInput.value = "";
    }

    async function newChat() {
        threadId = crypto.randomUUID();
        localStorage.setItem("thread_id", threadId);

        if (isDictating) {
            stopDictation();
        }

        renderWelcome();
        await loadConversations();
        messageInput.focus();
    }

    loadConversations();

    if (threadId) {
        loadConversation(threadId);
    }
