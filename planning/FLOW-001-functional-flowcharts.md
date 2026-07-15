# FLOW-001: Functional Flowchart

This flowchart describes how "A Penny Saved" handles impulse purchase entries, check-ins, savings statistics, and opportunity cost examples.

```mermaid
flowchart TD
    A[User opens A Penny Saved] --> B{Has account?}
    B -- No --> C[Sign up]
    B -- Yes --> D[Log in]
    C --> E[Dashboard]
    D --> E

    E --> F[User filters savings statistics]
    F --> G[App selects Saved items in date range]
    G --> H[App totals confirmed saved prices]
    H --> I[App counts avoided impulse purchases]
    I --> J[App displays filtered statistics]

    E --> K[User views opportunity cost]
    K --> L[App loads saved amount]
    L --> M[App loads comparison examples]
    M --> N[App divides saved amount by each example value]
    N --> O[App displays equivalent units saved]

    E --> P[User creates opportunity cost example]
    P --> Q[App validates label, unit name, and dollar value]
    Q --> R[App saves comparison example]
    R --> S[App makes example available for future calculations]

    E --> T[User adds impulse purchase]
    T --> U[App validates item name, price, and reason]
    U --> V[App records date added]
    V --> W[App creates entry with Waiting status]

    E --> X[User checks item after 48 hours]
    X --> Y[App confirms item is eligible for check-in]
    Y --> Z{User bought the item?}
    Z -- No --> AA[App saves optional comment]
    AA --> AB[App changes status to Saved]
    AB --> AC[App adds price to total saved]
    AC --> AD[App updates statistics and opportunity cost]
    Z -- Yes --> AE[App saves optional comment]
    AE --> AF[App changes status to Purchased]
    AF --> AG[App excludes price from total saved]
    AG --> AH[App includes item in purchase statistics]

    E --> AI[User edits Waiting item]
    AI --> AJ[App validates updated item details]
    AJ --> AK[App saves item changes]

    E --> AL[User deletes Waiting item]
    AL --> AM[App removes item from active purchase list]

    E --> AN[User picks a Saved entry]
    AN --> AO[User edits Saved or Purchased comment]
    AO --> AP[App updates comment only]
    AP --> AQ[App keeps item status and statistics unchanged]

    E --> AR[User opens hidden Purchased section]
    AR --> AS[App loads Purchased items]
    AS --> AT[App displays purchased entries separately from Saved total]
```
