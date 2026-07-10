A Penny Saved is a website that helps a user avoid impulse purchases by encouraging the user to wait 48 hours.

Core features:
- User can add a new impulse purchase entry with:
    - item name
    - price
    - date added
    - reason wanted
- New entries start as Waiting
- After 48 hours, users are prompted to check in manually.
    - There are two options:
    - "I did not buy it": the item moves to Saved and contributes to statistics
    - "I bought it": the item moves to a hidden section called "Purchased". It contributes to statistics but not the total Saved amount.
    - The user can also make an optional comment, which will appear in the entry when it moves to its respective location.
- Dashboard lists all purchase entries with status, price, date, and reason
- Statistics show avoided impulse purchases count and total money saved.
- Statistics can be filtered by this month, last 3 months, last 6 months, last year, and all-time.
- User can add comparable incoming income stream and typical cost examples.
    - For example, $20 per meal or $10 earned per hour.
- Opportunity cost statistics refers to how much money the user has saved in terms of a comparison example.
- Opportunity cost statistics compare how much the user saved against the user's predefined cost examples. 
    - Users can create examples with a label, unit name, and dollar value, such as "hours worked" at "$10/hour". The app will calculate and display messages like: "The amount you have saved is equal to X hours worked!"
    - Another example: 
- After the user indicates they did not buy an item for the 48 hour check-in, the item goes to the Saved section and the opportunity cost statistics update.
- Total amount saved include only confirmed Saved items.
- Users can edit entries while they are Waiting. They can also delete Waiting entries, and edit Saved/Purchased comments.
- The website should be responsive.
- The dashboard is split into 4 different sections:
    - Needs check-in: items where 48 hours have passed and user must answer if they bought the item or not. If yes, the item becomes Purchased. If not, the item is added to Saved. The user can also make a comment.
    - Waiting: items added less than 48 hours ago
    - Saved: items that the user did not buy
    - Purchased: items that the user indicated they bought during the check-in. It is hidden but can be manually opened at the bottom of the page.

User flow:
- User signs up or logs in. Users need real accounts.
- Main page/dashboard that lists all impulse purchases, statistics, and opportunity cost examples
- User clicks a button to add a new item on a separate screen.
- User returns after 48 hours and completes check-ins from the Needs check-in section.
- User can manage opportunity cost examples from a settings screen.