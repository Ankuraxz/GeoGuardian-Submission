# GeoGuardian-Submission
![tag : innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag : hackathon](https://img.shields.io/badge/hackathon-3D8BD3)

### A real-time emergency response dashboard built with Next.js, Firebase, Google Maps and a lots of AI Agents

## Inspiration
GeoGuardian was inspired by the devastating natural disasters, such as recent forest fires in Los Angeles, and the urgent need for sustainable climate action. These events highlighted the critical need for a tool to empower first responders, emergency services, and local authorities to act swiftly and effectively

Harnessing the power of AI and real-time data, GeoGuardian delivers vital information during emergencies, saving lives and protecting property. Its applications extend beyond natural disasters to medical emergencies like anxiety attacks and epileptic episodes, making it a versatile and life-saving platform

## What it does
GeoGuardian is a real-time emergency response dashboard that leverages AI and real-time data to provide critical information during emergencies. It empowers first responders, emergency services, and local authorities to act swiftly and effectively, ultimately saving lives and protecting property

It is a Next.js web application that integrates with Firebase for real-time data storage and Google Maps for location tracking. At the backend, it uses Twilio API and OpenAI Live Audio API as first responder to provide real-time communication between victims and emergency services

It also features 3 AI agents, namely OpenAI Agent (For reranking the data), Tailvy Agent (For web searches), and a custom Langraph based AI agent, to summarize conversation, and push it to firebase

When a Call Comes in :
* Twilio API receives a call from a victim and sends the audio to OpenAI Live Audio API for transcription and response
* The transcription is sent to the Langraph agent, which summarizes the conversation and pushes it to Firebase
* OpenAI Agent & Tailvy Agent are used to rerank the data and provide relevant information to the first responders
* If user cuts call, or network is dropped, or AI agent feels its highly critical, rank is increased and ticket is created
* In case th user wants to talk, or AI agent decides to calm down user, it continues conversation, while pushing a slightly lower rank ticket


As soon, as a new ticket is created in Firebase:
* Frontend will show the ticket in the dashboard.
* Location, Summary, Transcription, status, importance, and other details will be shown in the dashboard

Dashboard, also features a Historical section, with past data, analytics and satellite Images

## How we built it

We built GeoGuardian using Next.js for the frontend, Firebase for real-time data storage, and Google Maps for location tracking

The backend integrates Twilio API and OpenAI Live Audio API for real-time communication between victims and emergency services

We also utilized AI agents like OpenAI Agent, Tailvy Agent, and a custom Langraph agent to enhance the platform's functionality

## Accomplishments that we're proud of

We are proud of creating a real-time emergency response dashboard that effectively integrates multiple technologies and AI agents to provide critical information during emergencies. It is not here to replace first responders, but to assist them in their work, specially whe huge number of calls come in

## What we learned

Use of Agentverse, Fetch.ai and Langgraph , and their capabilities to create a custom agents 


## Agents used

### Custom Agents 
* **Langraph Agent**: This agent is responsible for summarizing conversations and pushing the data to Firebase. It uses the OpenAI Chat API to process the audio transcription and extract relevant information, summarize it and then push to Firebase

### Agentverse Agents
* **OpenAI Agent**: This agent is responsible for reranking the data and providing relevant information to the first responders
* **Tailvy Agent**: This agent is responsible for web searches and providing additional information to the first responders

### Custom Tools
* **Ticket Tool**: This tool is responsible for creating tickets in Firebase when a call comes in. It uses the Firebase API to create a new ticket with the relevant information
* **Transcription Tool**: This tool is responsible for transcribing the audio from the Twilio API


