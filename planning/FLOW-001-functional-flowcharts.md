# FLOW-001: Functional Flowchart

This flowchart describes how "A Penny Saved" handles impulse purchase entries, check-ins, savings statistics, and opportunity cost examples.

```mermaid
flowchart TD
    A[User opens A Penny Saved] --> B{Has account?}
    B -- No --> C[Sign up]
    B -- Yes --> D[Log in]
    C --> E[Dashboard]
    D --> E

    E --> F[View purchase entries by status]
    E --> G[View savings statistics]
    E --> H[View opportunity cost comparisons]
    E --> I[Manage opportunity cost examples]
    E --> J[Add impulse purchase]

    J --> K[Enter item name]
    K --> L[Enter price]
    L --> M[Enter reason wanted]
    M --> N[Save entry with date added]
    N --> O[Entry status: Waiting]
    O --> E

    F --> P{Has 48 hours passed?}
    P -- No --> Q[Keep item in Waiting section]
    P -- Yes --> R[Move item to Needs check-in section]
    Q --> E
    R --> S[Prompt user for manual check-in]

    S --> T{Did user buy it?}
    T -- No --> U[Optional comment]
    U --> V[Move item to Saved section]
    V --> W[Add item price to total saved]
    W --> X[Increase avoided purchase count]
    X --> Y[Update opportunity cost statistics]
    Y --> E

    T -- Yes --> Z[Optional comment]
    Z --> AA[Move item to hidden Purchased section]
    AA --> AB[Include item in purchase statistics]
    AB --> AC[Do not add price to total saved]
    AC --> E

    I --> AD[Create comparison example]
    AD --> AE[Enter label]
    AE --> AF[Enter unit name]
    AF --> AG[Enter dollar value per unit]
    AG --> AH[Save opportunity cost example]
    AH --> H

    H --> AI[Compare total saved against examples]
    AI --> AJ[Display equivalent units saved]
    AJ --> E

    G --> AK[Choose statistics filter]
    AK --> AL{Filter period}
    AL -- This month --> AM[Calculate filtered saved items]
    AL -- Last 3 months --> AM
    AL -- Last 6 months --> AM
    AL -- Last year --> AM
    AL -- All-time --> AM
    AM --> AN[Show total saved and avoided purchase count]
    AN --> E

    O --> AO{User edits or deletes while Waiting?}
    AO -- Edit --> AP[Update item details]
    AO -- Delete --> AQ[Remove Waiting item]
    AO -- No change --> E
    AP --> O
    AQ --> E

    V --> AR{User edits comment?}
    AA --> AR
    AR -- Yes --> AS[Update comment only]
    AR -- No --> E
    AS --> E
```
