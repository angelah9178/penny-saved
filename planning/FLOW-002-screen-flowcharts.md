# FLOW-002: Screen Flowchart

This flowchart describes the screens and user navigation for "A Penny Saved."

```mermaid
flowchart TD
    A[Landing / Welcome screen] --> B{User has account?}
    B -- No --> C[Sign up screen]
    B -- Yes --> D[Log in screen]
    C --> E[Dashboard screen]
    D --> E

    E --> F[Dashboard: Statistics summary]
    E --> G[Dashboard: Needs check-in section]
    E --> H[Dashboard: Waiting section]
    E --> I[Dashboard: Saved section]
    E --> J[Dashboard: Purchased section toggle]
    E --> K[Add item screen]
    E --> L[Settings screen]

    K --> M[New purchase form]
    M --> N[Item name field]
    N --> O[Price field]
    O --> P[Reason wanted field]
    P --> Q[Save item]
    Q --> E
    M --> R[Cancel]
    R --> E

    H --> S[Waiting item detail / edit screen]
    S --> T[Edit item name, price, or reason]
    T --> U[Save changes]
    U --> E
    S --> V[Delete Waiting item]
    V --> E
    S --> W[Cancel]
    W --> E

    G --> X[Check-in screen or modal]
    X --> Y[Review item details]
    Y --> Z[Optional comment field]
    Z --> AA{Check-in choice}
    AA -- I did not buy it --> AB[Saved confirmation]
    AA -- I bought it --> AC[Purchased confirmation]
    AB --> E
    AC --> E

    I --> AD[Saved item detail screen]
    AD --> AE[Edit comment]
    AE --> AF[Save comment]
    AF --> E
    AD --> AG[Back]
    AG --> E

    J --> AH{Purchased section open?}
    AH -- No --> AI[Keep Purchased hidden]
    AH -- Yes --> AJ[Show Purchased section]
    AJ --> AK[Purchased item detail screen]
    AK --> AL[Edit comment]
    AL --> AM[Save comment]
    AM --> E
    AK --> AN[Back]
    AN --> E
    AI --> E

    F --> AO[Statistics filter control]
    AO --> AP{Selected period}
    AP -- This month --> AQ[Refresh statistics view]
    AP -- Last 3 months --> AQ
    AP -- Last 6 months --> AQ
    AP -- Last year --> AQ
    AP -- All-time --> AQ
    AQ --> E

    L --> AR[Opportunity cost examples screen]
    AR --> AS[Examples list]
    AR --> AT[Add example form]
    AS --> AU[Edit example screen]
    AS --> AV[Delete example action]
    AT --> AW[Label field]
    AW --> AX[Unit name field]
    AX --> AY[Dollar value field]
    AY --> AZ[Save example]
    AZ --> L
    AU --> BA[Save edited example]
    BA --> L
    AV --> L
    L --> BB[Back to dashboard]
    BB --> E
```
