# FLOW-001: Functional Flowchart

This flowchart describes how "A Penny Saved" handles impulse purchase entries, check-ins, savings statistics, and opportunity cost examples.

```mermaid
flowchart TD
    A[User opens A Penny Saved] --> B{Has account?}
    B -- No --> C[Sign up]
    B -- Yes --> D[Log in]
    C --> E[Dashboard]
    D --> E

    E --> F[Top: total amount saved statistics]
    F --> G[Apply statistics filter]
    G --> H[Show avoided purchase count and total saved]
    H --> I[Show opportunity cost examples]
    I --> J[Calculate saved amount as equivalent units]
    J --> K[Needs check-in section]
    K --> L[List items where 48 hours have passed]
    L --> M[All impulse purchases section]
    M --> N[List item status, price, date, and reason]
    N --> O[Bottom: hidden Purchased section]
    O --> P[User can manually open Purchased items]

    I --> Q{Create new opportunity cost example?}
    Q -- Yes --> R[Open new opportunity cost example screen]
    R --> S[Enter label, unit name, and dollar value]
    S --> T[Save example]
    T --> U[Example is available for opportunity cost calculations]

    L --> V{Complete check-in?}
    V -- I did not buy it --> W[Add optional comment]
    W --> X[Move item to Saved]
    X --> Y[Add price to total saved]
    Y --> Z[Update statistics and opportunity cost calculations]
    V -- I bought it --> AA[Add optional comment]
    AA --> AB[Move item to hidden Purchased]
    AB --> AC[Include in purchase statistics only]

    M --> AD{Add new impulse purchase?}
    AD -- Yes --> AE[Open add item screen]
    AE --> AF[Enter item name, price, and reason]
    AF --> AG[Save entry with date added]
    AG --> AH[New entry starts as Waiting]

    M --> AI{Edit Waiting item?}
    AI -- Yes --> AJ[Update item details]
    M --> AK{Delete Waiting item?}
    AK -- Yes --> AL[Remove Waiting item]
    X --> AM{Edit Saved comment?}
    AM -- Yes --> AN[Update comment only]
    P --> AO{Edit Purchased comment?}
    AO -- Yes --> AP[Update comment only]
```
