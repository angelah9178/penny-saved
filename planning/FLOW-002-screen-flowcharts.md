# FLOW-002: Screen Flowchart

This flowchart describes the screens and user navigation for "A Penny Saved."

```mermaid
flowchart TD
    A[Landing / Welcome screen] --> B{User has account?}
    B -- No --> C[Sign up screen]
    B -- Yes --> D[Log in screen]
    C --> E[Dashboard screen]
    D --> E

    E --> F[User reviews total amount saved at top of dashboard]
    F --> G[User selects statistics filter]
    G --> H[User sees updated total saved and avoided purchase count]

    E --> I[User views opportunity cost examples]
    I --> J[User reads saved amount as equivalent meals, hours, or other units]

    E --> K[User clicks create opportunity cost example]
    K --> L[New opportunity cost example screen opens]
    L --> M[User enters label]
    M --> N[User enters unit name]
    N --> O[User enters dollar value]
    O --> P[User saves example]
    P --> Q[User sees save confirmation]

    E --> R[User reviews items that need check-in]
    R --> S[User opens check-in for an item]
    S --> T[User reviews item details]
    T --> U[User enters optional comment]
    U --> V{User chooses check-in result}
    V -- I did not buy it --> W[User sees Saved confirmation]
    V -- I bought it --> X[User sees Purchased confirmation]

    E --> Y[User reviews all impulse purchases]
    Y --> Z[User opens Waiting item details]
    Z --> AA{User chooses Waiting item action}
    AA -- Edit --> AB[User edits item name, price, or reason]
    AB --> AC[User saves item changes]
    AA -- Delete --> AD[User confirms deletion]
    AD --> AE[User sees delete confirmation]

    E --> AF[User clicks add new impulse purchase]
    AF --> AG[Add item screen opens]
    AG --> AH[User enters item name]
    AH --> AI[User enters price]
    AI --> AJ[User enters reason wanted]
    AJ --> AK[User saves item]
    AK --> AL[User sees item saved confirmation]

    E --> AM[User opens Saved item details]
    AM --> AN[User edits saved comment]
    AN --> AO[User saves comment]
    AO --> AP[User sees comment saved confirmation]

    E --> AQ[User opens hidden Purchased section]
    AQ --> AR[User opens Purchased item details]
    AR --> AS[User edits purchased comment]
    AS --> AT[User saves comment]
    AT --> AU[User sees comment saved confirmation]
```
