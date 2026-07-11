# FLOW-002: Screen Flowchart

This flowchart describes the screens and user navigation for "A Penny Saved."

```mermaid
flowchart TD
    A[Landing / Welcome screen] --> B{User has account?}
    B -- No --> C[Sign up screen]
    B -- Yes --> D[Log in screen]
    C --> E[Dashboard screen]
    D --> E

    E --> F{Choose screen or section}

    F -- Add item --> G[Add item screen]
    G --> H[New purchase form]
    H --> I[Item name, price, and reason fields]
    I --> J{Save or cancel?}
    J -- Save --> E
    J -- Cancel --> E

    F -- Needs check-in --> K[Check-in screen or modal]
    K --> L[Review item details]
    L --> M[Optional comment field]
    M --> N{Check-in choice}
    N -- I did not buy it --> O[Saved confirmation]
    N -- I bought it --> P[Purchased confirmation]
    O --> E
    P --> E

    F -- Waiting --> Q[Waiting item detail / edit screen]
    Q --> R{Edit, delete, or back?}
    R -- Edit --> S[Save item changes]
    R -- Delete --> T[Delete Waiting item]
    R -- Back --> E
    S --> E
    T --> E

    F -- Saved --> U[Saved item detail screen]
    U --> V{Edit comment or back?}
    V -- Edit comment --> W[Save comment]
    V -- Back --> E
    W --> E

    F -- Purchased --> X{Open hidden Purchased section?}
    X -- No --> E
    X -- Yes --> Y[Purchased item detail screen]
    Y --> Z{Edit comment or back?}
    Z -- Edit comment --> AA[Save comment]
    Z -- Back --> E
    AA --> E

    F -- Statistics --> AB[Statistics filter control]
    AB --> AC[Select this month, 3 months, 6 months, year, or all-time]
    AC --> AD[Refresh statistics summary]
    AD --> E

    F -- Settings --> AE[Opportunity cost examples screen]
    AE --> AF{Manage examples}
    AF -- Add --> AG[Example form]
    AG --> AH[Label, unit name, and dollar value fields]
    AH --> AI[Save example]
    AI --> AE
    AF -- Edit --> AJ[Edit example screen]
    AJ --> AK[Save edited example]
    AK --> AE
    AF -- Delete --> AE
    AF -- Back --> E
```
