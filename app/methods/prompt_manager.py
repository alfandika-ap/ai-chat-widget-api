import json
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

API_KEY = os.getenv("OPENAI_API_KEY")

openai_client = OpenAI(api_key=API_KEY)


class PromptManager:
    def __init__(self, model="gpt-4o-mini", messages=[]):
        self.model = model
        self.messages = messages

    def add_message(self, role, content):
        self.messages.append({"role": role, "content": content})

    def add_messages(self, messages):
        self.messages.extend(messages)

    def set_messages(selft, messages):
        selft.messages = messages

    def get_prompt(self):
        return {"model": self.model, "messages": self.messages}

    def generate(self, stream=False, functions=[]):
        kwargs = {
            "model": self.model,
            "messages": self.messages,
            "stream": stream,
        }

        if functions:
            kwargs["tools"] = [{"type": "function", "function": f} for f in functions]
            kwargs["tool_choice"] = "auto"  # penting agar model bisa memilih

        response = openai_client.chat.completions.create(**kwargs)

        if stream:
            return response
        else:
            message = response.choices[0].message
            if message.tool_calls:
                tool_call = message.tool_calls[0]
                return {
                    "type": "function_call",
                    "name": tool_call.function.name,
                    "arguments": json.loads(tool_call.function.arguments)
                }
            elif message.content:
                return  message.content
            else:
                return ""

    def generate_structured(self, schema):
        response = openai_client.beta.chat.completions.parse(
            model=self.model, messages=self.messages, response_format=schema
        )

        result = response.choices[0].message.model_dump()
        content = json.loads(result["content"])
        return content

    def generate_structured_json_schema(self, schema):
        function_schema = {
            "name": "extract_data",
            "description": "Extract structured data from the message.",
            "parameters": schema.model_json_schema()
        }

        response = openai_client.chat.completions.create(
            model=self.model,
            messages=self.messages,
            tools=[{
                "type": "function",
                "function": function_schema
            }],
            tool_choice="auto",
            temperature=0.2
        )

        tool_calls = response.choices[0].message.tool_calls
        if tool_calls:
            args = json.loads(tool_calls[0].function.arguments)
            return schema(**args)
        else:
            raise ValueError("No structured response generated.")