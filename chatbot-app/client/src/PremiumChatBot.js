import React, { useState, useRef, useEffect } from "react";
import ReactMarkdown from 'react-markdown';
import {
  PlusIcon,
  SendIcon,
  UserIcon,
  BotIcon,
  ChevronDownIcon,
  ThumbsUpIcon,
  ThumbsDownIcon,
  CopyIcon,
} from "lucide-react";

const PremiumChatBotUI = () => {
  const [conversations, setConversations] = useState([
    { id: 1, title: "New Conversation" },
    { id: 2, title: "Professional Bio Summary" },
    { id: 3, title: "Create a travel plan" },
    { id: 4, title: "Recommend a great book" },
  ]);
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState("");
  const messagesEndRef = useRef(null);
  const [isLoading, setIsLoading] = useState(false);
  const [feedback, setFeedback] = useState({});
  const initialized = useRef(false);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(scrollToBottom, [messages]);

  const handleSendMessage = async () => {
    if (inputMessage.trim() !== "") {
      setMessages([...messages, { text: inputMessage, sender: "user" }]);
      setInputMessage("");
      setIsLoading(true);

      try {
        const response = await fetch('/api/chat', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ message: inputMessage }),
        });

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        setMessages(prevMessages => [...prevMessages, { text: data.content, sender: "bot" }]);
        setIsLoading(false);
      } catch (error) {
        console.error('Error:', error);
        setMessages((prevMessages) => [
          ...prevMessages,
          {
            text: `Error: ${error.message}`,
            sender: "bot",
          },
        ]);
        setIsLoading(false);
      }
    }
  };

  const handleFeedback = (messageIndex, isPositive) => {
    setFeedback(prev => ({
      ...prev,
      [messageIndex]: isPositive
    }));
    // Here you would typically send this feedback to your backend
    console.log(`Feedback for message ${messageIndex}: ${isPositive ? 'positive' : 'negative'}`);
  };

  const handleCopyMessage = (text) => {
    navigator.clipboard.writeText(text).then(() => {
      // Optionally, you can show a brief notification that the text was copied
      console.log('Text copied to clipboard');
    }, (err) => {
      console.error('Could not copy text: ', err);
    });
  };

  const renderMessage = (message, index) => {
    return (
      <div
        key={index}
        className={`flex ${
          message.sender === "user" ? "justify-end" : "justify-start"
        } animate-fadeIn`}
      >
        <div
          className={`max-w-2xl p-4 rounded-2xl ${
            message.sender === "user"
              ? "bg-gradient-to-r from-purple-500 to-pink-500 text-white pt-3 pb-1 px-6 flex items-center"
              : "bg-gray-800 bg-opacity-50 text-gray-100"
          } shadow-xl flex`}
        >
          {message.sender === "bot" && (
            <BotIcon className="w-5 h-5 mr-3 mt-1 text-purple-400" />
          )}
          <div className="markdown-content">
            <ReactMarkdown>{message.text}</ReactMarkdown>
            
            {message.sender === "bot" && (
              <div className="mt-2 flex justify-end space-x-2">
                <button
                  onClick={() => handleCopyMessage(message.text)}
                  className="p-1 rounded-full bg-gray-700 hover:bg-gray-600"
                  title="Copy message"
                >
                  <CopyIcon className="w-4 h-4" />
                </button>
                <button
                  onClick={() => handleFeedback(index, true)}
                  className={`p-1 rounded-full ${feedback[index] === true ? 'bg-green-500' : 'bg-gray-700 hover:bg-gray-600'}`}
                >
                  <ThumbsUpIcon className="w-4 h-4" />
                </button>
                <button
                  onClick={() => handleFeedback(index, false)}
                  className={`p-1 rounded-full ${feedback[index] === false ? 'bg-red-500' : 'bg-gray-700 hover:bg-gray-600'}`}
                >
                  <ThumbsDownIcon className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  };

  // Function to add messages with delay and simulate movement
  const initializeMessages = async () => {
    const cities = [
      {
        user: "What's the difference between let and const in JavaScript?",
        bot: "Here's a simple explanation:\n\n" +
             "- `let` allows you to reassign values\n" +
             "- `const` prevents reassignment\n\n" +
             "Example:\n" +
             "```javascript\n" +
             "let count = 1;\n" +
             "count = 2; // ✅ This works\n\n" +
             "const API_KEY = '123';\n" +
             "API_KEY = '456'; // ❌ This throws an error\n" +
             "```"
      }
    ];

    // Add each city with a delay
    for (let i = 0; i < cities.length; i++) {
      const city = cities[i];
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      setMessages(prev => [
        ...prev,
        { sender: "user", text: city.user },
        { sender: "bot", text: city.bot }
      ]);
    }
  };

  // Call the initialization function when component mounts
  useEffect(() => {
    if (!initialized.current) {
      initialized.current = true;
      initializeMessages();
    }
  }, []);


  return (
    <div className="flex h-screen bg-gradient-to-br from-gray-900 via-purple-900 to-indigo-900 text-gray-100 font-sans">
      {/* Sidebar */}
      <div className="w-80 bg-black bg-opacity-30 backdrop-filter backdrop-blur-lg p-6 flex flex-col border-r border-gray-800">
        <button className="bg-gradient-to-r from-pink-500 via-purple-500 to-indigo-500 text-white rounded-full py-3 px-6 flex items-center justify-center mb-8 hover:from-pink-600 hover:via-purple-600 hover:to-indigo-600 transition-all duration-300 shadow-lg transform hover:scale-105">
          <PlusIcon className="w-5 h-5 mr-2" />
          <span className="font-semibold">New Chat</span>
        </button>
        <div className="flex-grow overflow-y-auto space-y-2 custom-scrollbar">
          {conversations.map((conv) => (
            <div
              key={conv.id}
              className="py-3 px-4 rounded-lg hover:bg-white hover:bg-opacity-10 cursor-pointer transition-all duration-200 flex items-center group"
            >
              <UserIcon className="w-5 h-5 mr-3 text-gray-400 group-hover:text-purple-400" />
              <span className="text-sm font-medium group-hover:text-purple-300">
                {conv.title}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col bg-black bg-opacity-50 backdrop-filter backdrop-blur-md">
        {/* Messages */}
        <div className="flex-grow overflow-y-auto p-8 space-y-6 custom-scrollbar">
          {messages.map((message, index) => renderMessage(message, index))}
          {isLoading && (
            <div className="flex justify-center items-center py-4">
              <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-purple-500"></div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="border-t border-gray-800 p-6">
          <div className="flex items-center bg-gray-800 bg-opacity-50 rounded-full shadow-inner backdrop-filter backdrop-blur-sm">
            <input
              type="text"
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyPress={(e) => e.key === "Enter" && handleSendMessage()}
              className="flex-grow px-6 py-4 bg-transparent outline-none text-gray-100 placeholder-gray-400"
              placeholder="Message ChatBot..."
            />
            <button
              onClick={handleSendMessage}
              className="p-3 rounded-full text-gray-400 hover:text-purple-400 transition-colors duration-200 mr-2"
            >
              <SendIcon className="w-5 h-5 transform rotate-45" />
            </button>
          </div>
          <div className="text-xs text-gray-500 mt-3 text-center flex items-center justify-center">
            <ChevronDownIcon className="w-4 h-4 mr-1" />
            ChatBot may produce inaccurate information about people, places, or
            facts.
          </div>
        </div>
      </div>
    </div>
  );
};

export default PremiumChatBotUI;