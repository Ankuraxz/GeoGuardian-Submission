from typing import Any
from uagents import Agent, Context, Model


class ContextPrompt(Model):
    context: str
    text: str


class Response(Model):
    text: str


class StructuredOutputPrompt(Model):
    prompt: str
    output_schema: dict[str, Any]


class StructuredOutputResponse(Model):
    output: dict[str, Any]


agent = Agent()


AI_AGENT_ADDRESS = "test-agent://agent1q0h70caed8ax769shpemapzkyk65uscw4xwk6dc4t3emvp5jdcvqs9xs32y"


code = """
    def do_something():
        for i in range(10)
            pass
    """

prompt = ContextPrompt(
    context="Find and fix the bug in the provided code snippet",
    text=code,
)

class Location(Model):
    city: str
    country: str
    temperature: float


prompts = [
    ContextPrompt(
        context="Find and fix the bug in the provided code snippet",
        text=code,
    ),
    StructuredOutputPrompt(
        prompt="How is the weather in London today?",
        output_schema=Location.schema(),
    ),
]


@agent.on_event("startup")
async def send_message(ctx: Context):
    for prompt in prompts:
        await ctx.send(AI_AGENT_ADDRESS, prompt)


@agent.on_message(Response)
async def handle_response(ctx: Context, sender: str, msg: Response):
    ctx.logger.info(f"Received response from {sender}: {msg.text}")


@agent.on_message(StructuredOutputResponse)
async def handle_structured_output_response(ctx: Context, sender: str, msg: StructuredOutputResponse):
    ctx.logger.info(f"[Received response from ...{sender[-8:]}]:")
    response = Location.parse_obj(msg.output)
    ctx.logger.info(response)


if __name__ == "__main__":
    agent.run()
