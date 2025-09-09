AVG_WORDS_PER_CONVERSATION = 1000
class Message:
    def __init__(self, sender, recipient, text, opinion_about_recipient=None):
        """
        Constructor for Message.

        Args:
            sender (str): The sender of the message.
            recipient (str): The recipient of the message.
            text (str): The text of the message.
            opinion_about_recipient (str, optional): The opinion of the sender about the recipient. Defaults to None.
        """
        self.sender = sender
        self.recipient = recipient
        self.text = text
        self.opinion = opinion_about_recipient

    def __str__(self):
        """
        Converts the message into a string format.

        The string representation of the message shows the sender, recipient, text and opinion of the sender about the recipient.

        Returns:
            str: The string representation of the message.
        """

        t = f"""{self.sender} to {self.recipient}: {self.text} \n"""
        if self.opinion:
            t += f""" Opinion on of {self.sender} about {self.recipient} is {self.opinion}"""
            t += "\n"
        return t

    def to_dict(self):
        """
        Converts the message into a dictionary format.

        Returns:
            dict: The dictionary representation of the message.
        """
        return {
            "sender": self.sender,
            "recipient": self.recipient,
            "text": self.text,
            "opinion": self.opinion,
        }

    def message_to_prompt(self, message):
        """
        Converts the message into a string prompt format.

        The prompt string contains the sender of the message and the text of the message.

        Args:
            message (str): The message to be converted into a prompt string.

        Returns:
            str: The prompt string.
        """
        prompt = f""" {self.sender} says: {message} """
        return prompt

    def get_word_count(self):
        """
        Returns the number of words in the message.

        Returns:
            int: The number of words in the message.
        """
        return len(self.text.split())


class DialogueAgent:
    next_dialogue_number: int = 0

    def __init__(
        self,
        initiator_name,
        responder_name,
        day,
        time,
        location,
        initiator_reputation=None,
        recipient_reputation=None,
        dialogue_number=None,
        reputation_enabled=None
    ):
        if dialogue_number is not None:
            self.dialogue_number = dialogue_number
            DialogueAgent.next_dialogue_number = dialogue_number + 1
        else:
            self.dialogue_number = (
                DialogueAgent.next_dialogue_number
            )  # Assign the current number
        DialogueAgent.next_dialogue_number += 1  # Increment for the next dialogue
        self.messages = []
        self.initiator_name = initiator_name
        self.initiator_reputation = initiator_reputation
        self.recipient_reputation = recipient_reputation
        self.responder_name = responder_name
        self.day = day
        self.time = time
        self.location = location
        self.initiator_word_counter = 0
        self.responder_word_counter = 0
        self.dialogue_context_counter = 0
        self.dialogue_ending_prob = 0
        self.goodbye_count = 0
        self.reputation_enabled = reputation_enabled

    def add_message(self, message: Message):
        self.messages.append(message)
        self.dialogue_context_counter += message.get_word_count()
        logging.info(f"Dialogue message len: {self.dialogue_context_counter}")
        self.dialogue_ending_prob = float(poisson.cdf(
            k=self.dialogue_context_counter, mu=AVG_WORDS_PER_CONVERSATION
        ))

    def dialogue_limit(self):
        prompt = ""
        if self.dialogue_ending_prob < 0.5:
            prompt += f""" You are at the beginning of the conversation\n"""
        elif 0.4 <= self.dialogue_ending_prob <= 0.7:
            prompt += f""" You are in the middle of the conversation prepare to wrap up\n"""
        elif 0.7 < self.dialogue_ending_prob < 0.8:
            prompt += f""" You are at the end of the conversation. Wrap up the topic\n"""
        elif 0.8 <= self.dialogue_ending_prob < 0.9:
            prompt += f""" You are at the end of conversation immediately say GOODBYE. You need to end the conversation saying "GOODBYE"\n"""
        elif 0.9 <= self.dialogue_ending_prob <= 1.0:
            prompt += f""" You are at the end of conversation immediately say GOODBYE. You need to end the conversation saying "GOODBYE"\n"""
            self.goodbye_count += 1
        return prompt

    def __str__(self):
        t = f"""Dialogue number is {self.dialogue_number}, Dialogue initiator is {self.initiator_name}, responder is {self.responder_name}, day={self.day}, time={self.time}, location={self.location}"""
        for m in self.messages:
            t += f"""\n{str(m)}"""
        return t

    def to_dict(self):
        """
        Converts the Dialogue object to a dictionary.

        Returns:
            dict: The dictionary representation of the Dialogue object.
        """
        return {
            "dialogue_number": self.dialogue_number,
            "initiator_name": self.initiator_name,
            "initiator_reputation": self.initiator_reputation,
            "recipient_reputation": self.recipient_reputation,
            "responder_name": self.responder_name,
            "day": self.day,
            "time": self.time,
            "location": self.location,
            "messages": [message.to_dict() for message in self.messages],
            "initiator_word_counter": self.initiator_word_counter,
            "responder_word_counter": self.responder_word_counter,
            "dialogue_context_counter": self.dialogue_context_counter,
            "dialogue_ending_prob": self.dialogue_ending_prob,
            "goodbye_count": self.goodbye_count,
        }
    
