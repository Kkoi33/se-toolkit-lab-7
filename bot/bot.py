#!/usr/bin/env python3
import os
import sys
import json
import requests
import asyncio
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

# Load environment variables
load_dotenv()

# Configuration
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
LLM_API_BASE = os.getenv("LLM_API_BASE_URL", "http://localhost:42005")
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_MODEL = os.getenv("LLM_API_MODEL", "qwen")
BACKEND_URL = "http://localhost:8000"  # Adjust if needed

# System prompt encouraging tool use
SYSTEM_PROMPT = """You are a helpful assistant that can query lab data. 
When users ask about labs, scores, learners, or analytics, use the available tools to fetch real data.
Always use tools to get current data - don't make up information.
If a user asks a question that requires multiple steps (like finding the lab with lowest pass rate), 
call get_items first to see all labs, then call get_pass_rates for each lab to compare.
Format responses clearly with emojis and bullet points where appropriate.
If a user says hello or sends gibberish, respond helpfully explaining what you can do."""

# Define 9+ tools as required
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_items",
            "description": "Get list of all labs and their tasks",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_learners",
            "description": "Get list of enrolled students and their groups",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_scores",
            "description": "Get score distribution (4 buckets) for a specific lab",
            "parameters": {
                "type": "object",
                "properties": {
                    "lab": {
                        "type": "string",
                        "description": "Lab identifier, e.g., 'lab-01'"
                    }
                },
                "required": ["lab"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_pass_rates",
            "description": "Get per-task average scores and attempt counts for a lab",
            "parameters": {
                "type": "object",
                "properties": {
                    "lab": {
                        "type": "string",
                        "description": "Lab identifier, e.g., 'lab-01'"
                    }
                },
                "required": ["lab"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_timeline",
            "description": "Get submissions per day for a specific lab",
            "parameters": {
                "type": "object",
                "properties": {
                    "lab": {
                        "type": "string",
                        "description": "Lab identifier, e.g., 'lab-01'"
                    }
                },
                "required": ["lab"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_groups",
            "description": "Get per-group scores and student counts for a lab",
            "parameters": {
                "type": "object",
                "properties": {
                    "lab": {
                        "type": "string",
                        "description": "Lab identifier, e.g., 'lab-01'"
                    }
                },
                "required": ["lab"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_learners",
            "description": "Get top N learners by score for a specific lab",
            "parameters": {
                "type": "object",
                "properties": {
                    "lab": {
                        "type": "string",
                        "description": "Lab identifier, e.g., 'lab-01'"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of top learners to return, default 5"
                    }
                },
                "required": ["lab"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_completion_rate",
            "description": "Get completion rate percentage for a specific lab",
            "parameters": {
                "type": "object",
                "properties": {
                    "lab": {
                        "type": "string",
                        "description": "Lab identifier, e.g., 'lab-01'"
                    }
                },
                "required": ["lab"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "trigger_sync",
            "description": "Refresh data from autochecker by triggering sync",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]

class Bot:
    def __init__(self):
        self.conversations = {}  # Store conversation history per user
        
    def call_backend_api(self, endpoint: str, method: str = "GET", data: Dict = None) -> Dict:
        """Make real backend API calls"""
        try:
            url = f"{BACKEND_URL}{endpoint}"
            if method == "GET":
                response = requests.get(url, timeout=5)
            else:
                response = requests.post(url, json=data, timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"[ERROR] Backend API call failed: {e}", file=sys.stderr)
            return {"error": str(e)}
    
    # Tool implementations - each calls real backend API
    def get_items(self) -> Dict:
        return self.call_backend_api("/items/")
    
    def get_learners(self) -> Dict:
        return self.call_backend_api("/learners/")
    
    def get_scores(self, lab: str) -> Dict:
        return self.call_backend_api(f"/analytics/scores?lab={lab}")
    
    def get_pass_rates(self, lab: str) -> Dict:
        return self.call_backend_api(f"/analytics/pass-rates?lab={lab}")
    
    def get_timeline(self, lab: str) -> Dict:
        return self.call_backend_api(f"/analytics/timeline?lab={lab}")
    
    def get_groups(self, lab: str) -> Dict:
        return self.call_backend_api(f"/analytics/groups?lab={lab}")
    
    def get_top_learners(self, lab: str, limit: int = 5) -> Dict:
        return self.call_backend_api(f"/analytics/top-learners?lab={lab}&limit={limit}")
    
    def get_completion_rate(self, lab: str) -> Dict:
        return self.call_backend_api(f"/analytics/completion-rate?lab={lab}")
    
    def trigger_sync(self) -> Dict:
        return self.call_backend_api("/pipeline/sync", method="POST")
    
    def call_llm(self, messages: List[Dict], tools: List[Dict] = None) -> Dict:
        """Call LLM API with tool support"""
        headers = {
            "Authorization": f"Bearer {LLM_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": LLM_MODEL,
            "messages": messages,
            "temperature": 0.1
        }
        
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        
        try:
            response = requests.post(
                f"{LLM_API_BASE}/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"[ERROR] LLM call failed: {e}", file=sys.stderr)
            return {"error": str(e)}
    
    def execute_tool(self, tool_name: str, arguments: Dict) -> Any:
        """Execute a tool and return result"""
        print(f"[tool] LLM called: {tool_name}({arguments})", file=sys.stderr)
        
        try:
            if tool_name == "get_items":
                result = self.get_items()
            elif tool_name == "get_learners":
                result = self.get_learners()
            elif tool_name == "get_scores":
                result = self.get_scores(**arguments)
            elif tool_name == "get_pass_rates":
                result = self.get_pass_rates(**arguments)
            elif tool_name == "get_timeline":
                result = self.get_timeline(**arguments)
            elif tool_name == "get_groups":
                result = self.get_groups(**arguments)
            elif tool_name == "get_top_learners":
                result = self.get_top_learners(**arguments)
            elif tool_name == "get_completion_rate":
                result = self.get_completion_rate(**arguments)
            elif tool_name == "trigger_sync":
                result = self.trigger_sync()
            else:
                result = {"error": f"Unknown tool: {tool_name}"}
            
            print(f"[tool] Result: {str(result)[:200]}...", file=sys.stderr)
            return result
        except Exception as e:
            print(f"[tool] Error: {e}", file=sys.stderr)
            return {"error": str(e)}
    
    def process_query(self, user_id: str, query: str) -> str:
        """Main processing loop with tool calling"""
        # Initialize or get conversation
        if user_id not in self.conversations:
            self.conversations[user_id] = [
                {"role": "system", "content": SYSTEM_PROMPT}
            ]
        
        # Add user message
        self.conversations[user_id].append({"role": "user", "content": query})
        
        # Tool calling loop
        max_iterations = 5
        for iteration in range(max_iterations):
            print(f"[iteration] {iteration + 1}", file=sys.stderr)
            
            # Call LLM
            response = self.call_llm(self.conversations[user_id], TOOLS)
            
            if "error" in response:
                return f"Error: {response['error']}"
            
            message = response["choices"][0]["message"]
            
            # Check if LLM wants to call tools
            if message.get("tool_calls"):
                # Add assistant message with tool calls
                self.conversations[user_id].append(message)
                
                # Execute each tool call
                for tool_call in message["tool_calls"]:
                    function_name = tool_call["function"]["name"]
                    arguments = json.loads(tool_call["function"]["arguments"])
                    
                    result = self.execute_tool(function_name, arguments)
                    
                    # Add tool result to conversation
                    self.conversations[user_id].append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": json.dumps(result)
                    })
                
                # Continue loop to get final answer
                continue
            
            # No tool calls, this is the final answer
            final_answer = message["content"]
            self.conversations[user_id].append(message)
            print(f"[summary] Final answer generated", file=sys.stderr)
            return final_answer
        
        return "I'm having trouble processing that request. Please try again."
    
    def get_keyboard(self) -> InlineKeyboardMarkup:
        """Create inline keyboard with buttons"""
        keyboard = [
            [InlineKeyboardButton("📚 View All Labs", callback_data="get_items")],
            [InlineKeyboardButton("👥 View Learners", callback_data="get_learners")],
            [InlineKeyboardButton("📊 Lab Scores", callback_data="get_scores")],
            [InlineKeyboardButton("✅ Pass Rates", callback_data="get_pass_rates")],
            [InlineKeyboardButton("📈 Top Learners", callback_data="get_top_learners")],
            [InlineKeyboardButton("🏆 Group Performance", callback_data="get_groups")],
            [InlineKeyboardButton("📅 Timeline", callback_data="get_timeline")],
            [InlineKeyboardButton("🎯 Completion Rate", callback_data="get_completion_rate")],
            [InlineKeyboardButton("🔄 Sync Data", callback_data="trigger_sync")],
            [InlineKeyboardButton("❓ Help", callback_data="help")]
        ]
        return InlineKeyboardMarkup(keyboard)

# Global bot instance
bot_instance = Bot()

# Telegram handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    welcome_text = (
        "🤖 *Lab Data Assistant Bot*\n\n"
        "I can help you query lab data using natural language!\n\n"
        "Try asking:\n"
        "• \"what labs are available?\"\n"
        "• \"which lab has the lowest pass rate?\"\n"
        "• \"show me top 5 learners in lab 4\"\n"
        "• \"how many students are enrolled?\"\n\n"
        "Or use the buttons below to get started!"
    )
    await update.message.reply_text(
        welcome_text,
        reply_markup=bot_instance.get_keyboard(),
        parse_mode="Markdown"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle plain text messages"""
    user_id = str(update.effective_user.id)
    query = update.message.text
    
    # Process the query
    response = bot_instance.process_query(user_id, query)
    
    await update.message.reply_text(response, reply_markup=bot_instance.get_keyboard())

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard button presses"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(update.effective_user.id)
    button_data = query.data
    
    # Map buttons to natural language queries
    button_map = {
        "get_items": "what labs are available?",
        "get_learners": "how many students are enrolled?",
        "get_scores": "show me scores for lab 01",
        "get_pass_rates": "show me pass rates for lab 01",
        "get_top_learners": "who are the top 5 learners in lab 01?",
        "get_groups": "which group is doing best in lab 01?",
        "get_timeline": "show me submission timeline for lab 01",
        "get_completion_rate": "what is the completion rate for lab 01?",
        "trigger_sync": "sync the data",
        "help": "help"
    }
    
    natural_query = button_map.get(button_data, button_data)
    
    # Process the query
    response = bot_instance.process_query(user_id, natural_query)
    
    await query.edit_message_text(
        response,
        reply_markup=bot_instance.get_keyboard()
    )

def test_mode():
    """Run in test mode for command-line testing"""
    if len(sys.argv) < 2:
        print("Usage: uv run bot.py --test 'your query here'")
        sys.exit(1)
    
    query = " ".join(sys.argv[2:])
    print(f"Testing query: {query}", file=sys.stderr)
    
    response = bot_instance.process_query("test_user", query)
    print(response)

def main():
    """Main entry point"""
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_mode()
    else:
        # Run Telegram bot
        app = Application.builder().token(TELEGRAM_TOKEN).build()
        
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        app.add_handler(CallbackQueryHandler(handle_button))
        
        print("Bot is running...", file=sys.stderr)
        app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()