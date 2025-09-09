# this is a text based game. no actions or any other mechanisms there is only location, time and characters. And the characters are NPCs. Game run by itself NPCs talk to each other based on scheduler. 

# on the database side we have sqlite database. A database to hold long term memory of the game. By long term memory we mean each conversation between two NPCs. which session they occured in, who started the conversation, who is the receiver, what is the conversation summary. Also metadata for the session, so without loss I can retrieve all conversations of a session but also NPCs. Don't forget that NPCs can be introduced in the game by lifecycle agent so not everyday every NPC exists. I should be able to import conversation history of a session to the database and frontend chatbox. Another important thing is that metadata of the session should be stored in the database including plaintext conversation text,total conversation text length, conversation summary(text, we will apply a summarizer function later when the context is above a threshold), conversation summary length(to validate the summary is not passing certain token length) this summary method is for not to exceed the token limit of the LLM. because game history will surpass this at some degree. 

# below is the database design in my mind. 
# a message has: sender, reciever, conversation_id, sender_opinion, receiver_opinion, message_text, message_id
# a conversation has: conversation_id, initiator, receiver, message_ids, session_id, day, time_period
# a session has conversations and NPCs and all other metadata and long term memory, summary.

# there is also an abstraction over the database to make it easier to access the database. 
# there is mechanism for NPC to reach it's own memories(conversations) in the session.
# Each npc has a memory object that it can use to access it's own memories. Each NPC will have a database entry in the long term memory for it's own memory. Each NPC will also have memory summary mechanism for context limit.


# each agent should run on their own thread/api and should be able to access the database and other agents. For example schedule agent can send a message to dialogue agent to start a dialogue. Dialogue agent runs the dialogue, while running it it should update the memory agent and also update the frontend chatbox using SSE. 
# The agents are divided in two main categories
# Utility agents that makes decisions and keep information structure 
#   1. Game manager agent
#   2. NPC manager agent: 
#        - hold all NPCs as objects and keep them in memory also modify the properties.
#        - Initialize new npcs from lifecycle agent if they are introduced. 
#   3. Dialogue manager agent
#        - hold all dialogues as objects and keep them in memory also modify the properties.
#        - manage active context of dialogues. Ie ongoing dialogue doesn't go to long term memory which is database but short term memory. 
#        - frontend chatbox consistency with the ongoing dialogue. Because frontend sohuld display both history and current dialogue dynamically. 
#   4. Memory agent
#        - hold all memories as objects and keep them in memory also modify the properties.
# Game flow agents
#   These agents require llm provider and will get the related api key from .env file
#   1. lifecycle agent decides which agent is active or passive on which day also decides if need to introduce new NPC charater to the game
#        - dummy implementation: take all information as input but ignore it and select one
#        - data it requires for prompt are: 
#               most recent conversation between two NPCS < from dialogue agent. dialouge context
#               conversation summary of all game < from memory agent
#               reputations of all agents < from reputation agent
#               list of NPCs talked with each other current day < from game context agent
#         - output:
#               JSON: {list of active characters}
#               JSON: {if there is new character fill this otherwise false}
#   2. schedule agent decides which agent will act next and talk with whom
#        - dummy implementation: take all information as input but ignore it and select two at random
#        - data it requires for prompt are: 
#               most recent conversation between two NPCS
#               conversation summary of all game
#               reputations of all agents
#               list of NPCs talked with each other current day
#       - output:
#               tuple: (next NPC to act, next NPC to talk with) this dialogue initiator and receiver

# Social Agents
#   1. Opinion agent: 
#         - data: current conversation history not the long term memory < dialogue manager agent 

