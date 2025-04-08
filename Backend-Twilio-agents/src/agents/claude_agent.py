from typing import Any
from uagents import Agent, Context, Model


class TextPrompt(Model):
    text: str


class TextResponse(Model):
    text: str


class StructuredOutputPrompt(Model):
    prompt: str
    output_schema: dict[str, Any]


class StructuredOutputResponse(Model):
    output: dict[str, Any]


agent = Agent()


AI_AGENT_ADDRESS = "test-agent://agent1qvk7q2av3e2y5gf5s90nfzkc8a48q3wdqeevwrtgqfdl0k78rspd6f2l4dx"


class Location(Model):
    city: str
    country: str
    temperature: float


prompts = [
    TextPrompt(text="Compare the inflation rates of the past years in various European countries."),
    StructuredOutputPrompt(
        prompt="How is the weather in London today?",
        output_schema=Location.schema(),
    ),
]


@agent.on_event("startup")
async def send_message(ctx: Context):
    for prompt in prompts:
        await ctx.send(AI_AGENT_ADDRESS, prompt)
        ctx.logger.info(f"[Sent prompt to AI agent]: {prompt}")


@agent.on_message(TextResponse)
async def handle_response(ctx: Context, sender: str, msg: TextResponse):
    ctx.logger.info(f"[Received response from ...{sender[-8:]}]:")
    ctx.logger.info(msg.text)


@agent.on_message(StructuredOutputResponse)
async def handle_response(ctx: Context, sender: str, msg: StructuredOutputResponse):
    ctx.logger.info(f"[Received response from ...{sender[-8:]}]:")
    ctx.logger.info(msg.output)
    response = Location.parse_obj(msg.output)
    ctx.logger.info(response)


if __name__ == "__main__":
    agent.run()
