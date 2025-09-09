The frontend should be modified for experimental use. As admin I should still reach to this one bur non-admin users which are test subject shouldnt see:
1. Control panel
2. Admin and the buttons nearby it. 

This will be done as minor modification as possible. 

When user enters the game there will a modal showing the USER_STUDY_GUIDE.md. This is same with the guide button that user can click anytime during the game. 


There will be questionarie mechanism like qualtrics we will have 4 questionaries in total loaded from a csv file and each questionarie will be saved with user id in the game and the questionarie id in the game. This is coherent with maingamedata.db. 

Experiment implementation:
Test buttons will be modied too: In the backend we still keep same structure of sessions but frontend will only use test1, test2, test5 and test6. These will be renamed as Session1-part1, Session1-part2, Session2-part1 and Session2-part2. Only Session1-part1 is clickable rest will be autotriggered. 

Limit mechanism: 
There is a time starts from 0 at the beginning of each session, user can see it at top rigth of the chatbox. 
When the user sent message number hits at least 20 and the time spent passes 10 mins in the session part the condition to get to next part is satisfied. This is how user can navigate:   Session1-part1 button deactivates and Session1-part2 activates very visibly. Then user clicks to proceed next. When Session1-part2 hits the message limit there will be session1 survey triggered. After survery done session2-part1 button enabled. After session2-part1 hits usermessage limit session2-part2 button enabled. after session2-part ended session2 questionarie modal opens. After questionarie ends the final questionarie happens. 

Make this part safe so user can't trick us okay? 