# Testing Business Programs Without Constructing Domain Objects

Unit testing business logic often requires surprisingly little business data.

Suppose we want to test a program that loads an order, calculates its total, and rejects it when the amount exceeds a limit. The decision we want to verify is simple:

1. The program loads the specified order.
2. It asks for the order’s total.
3. If the total is too high, it does not approve the order.
4. It returns `FALSE`.

Yet a conventional Java unit test may have to construct an `Order`. That order may require a customer, line items, currencies, prices, tax information, identifiers and other objects that have nothing to do with the decision being tested.

Builders, fixtures and mocking frameworks reduce the typing, but they do not eliminate the underlying problem: the test must participate in the internal representation of the domain model.

BUBAS takes a different approach. Domain objects are opaque to a BUBAS program. Because the program cannot inspect them, a unit test does not need to construct them.

It needs only a token.

## The business program

Consider this BUBAS program:

```basic
PROGRAM ApproveOrder(orderId INTEGER, limit DECIMAL) RETURNS BOOLEAN
    DECLARE purchase Order
    DECLARE total DECIMAL

    purchase = LOAD_ORDER(orderId)

    IF NOT ORDER_WAS_FOUND(purchase) THEN
        LOG_EVENT "ERROR", "no such order: " + orderId
        RETURN FALSE
    END IF

    total = ORDER_TOTAL(purchase)

    IF total > limit THEN
        LOG_EVENT "INFO", "over limit: " + total
        RETURN FALSE
    END IF

    APPROVE purchase
    RETURN TRUE
END.
```

`Order` is a Java domain type registered by the application embedding BUBAS. The program can store an `Order` in a variable and pass it to operations that accept an `Order`, but it cannot access its fields or invoke its methods.

There is no expression such as:

```text
purchase.customer.account.balance
```

If the program needs information about an order, the application must expose an operation for obtaining it:

```basic
total = ORDER_TOTAL(purchase)
```

This restriction is primarily an encapsulation mechanism. The business program depends on the vocabulary of its domain rather than on the internal structure of Java objects.

It also has an important consequence for testing.

## Replace the object with identity

Here is a BUNIT test for the over-limit case:

```basic
PROGRAM OverLimitIsRejected
    "LOAD_ORDER"  WITH ARGS(42)   RETURNS "o1"
    "ORDER_TOTAL" WITH ARGS("o1") RETURNS 1500.00
    "APPROVE _" IS MOCKED

    ARGUMENT "orderId" IS 42
    ARGUMENT "limit"   IS 1000.00

    RUN

    RESULT IS FALSE
    "APPROVE _" WAS NOT CALLED
END.
```

The string `"o1"` is not an order serialized as text. It does not contain an order number, a total or any other property. It is a test token representing one opaque `Order`.

The first mock says:

```basic
"LOAD_ORDER" WITH ARGS(42) RETURNS "o1"
```

When the program calls `LOAD_ORDER(42)`, BUNIT returns the token `"o1"` in place of the real Java object.

The program stores it in `purchase`. Later it calls:

```basic
ORDER_TOTAL(purchase)
```

The second mock recognizes that same token and returns `1500.00`.

The program cannot tell that `"o1"` is not a real `Order`. It has no operation with which to inspect the object. It can only pass the value back through the vocabulary supplied by the host application.

For this test, identity is all the domain object needs.

## We are testing the conversation

A BUBAS business program contains decisions and orchestration. Algorithms, persistence, infrastructure and domain-object implementations remain in Java.

Its unit test should therefore concentrate on questions such as:

* Which domain operations were invoked?
* With what arguments?
* What values did those operations return?
* Which branch did the program select?
* Which operations were deliberately not invoked?
* What result did the program produce?

In the example, we do not test how `ORDER_TOTAL` calculates a total. That belongs in the Java test for the implementation of `ORDER_TOTAL`.

We test what the business program does when `ORDER_TOTAL` reports `1500.00`.

This division gives us two focused tests rather than one oversized test:

* Java tests verify the individual domain operations.
* BUNIT tests verify how a business program coordinates them.

The BUNIT test documents the business scenario directly. An order identified by `42` exists, its total is `1500.00`, the approval limit is `1000.00`, and the program must not approve it.

The test does not explain how to manufacture an object graph capable of producing those facts.

## Opacity buys mockability

Mocking domain objects in a general-purpose language is often difficult precisely because the production code can observe so much about them.

It may call methods, inspect nested objects, compare values, serialize the object or pass it to code that expects a particular implementation. A substitute must reproduce every observable property used along the tested path.

An opaque BUBAS value has only the observations provided by the registered vocabulary. If the vocabulary exposes `ORDER_TOTAL`, then the mock controls the answer to `ORDER_TOTAL`. If it does not expose the customer’s internal account object, neither the program nor the test needs to know that such an object exists.

The object boundary and the testing boundary are the same boundary.

This is stronger than merely saying that business programs should avoid inspecting domain objects. They cannot inspect them unless the embedder deliberately provides an operation that does so.

Consequently, a token can stand in for any opaque value as long as the mocks define how the exposed operations respond to it.

Multiple objects require only multiple identities:

```basic
"LOAD_ORDER" WITH ARGS(42) RETURNS "o1"
"LOAD_ORDER" WITH ARGS(43) RETURNS "o2"

"ORDER_TOTAL" WITH ARGS("o1") RETURNS 1500.00
"ORDER_TOTAL" WITH ARGS("o2") RETURNS 200.00
```

The test describes the distinctions that matter without constructing either order.

## The test uses the real language

A dangerous form of mocking creates a second, simplified interface used only by tests. Eventually the production vocabulary changes while the test vocabulary does not.

BUNIT does not compile the business program against a parallel language. The program under test is compiled against the real sealed BUBAS language. Mocking happens later, at dispatch.

Therefore, the test cannot silently keep using an operation that no longer exists in the production language. Nor can it casually return a value of the wrong BUBAS type.

Before executing a test, BUNIT checks the mocks and the test configuration. It can report problems such as:

* a mock declared with the wrong number of arguments;
* a mock returning a value incompatible with the real operation;
* an argument supplied for a parameter the program does not accept;
* a mocked command that should initialize a variable but does not provide its value.

These errors are reported in the test before the business program runs.

The test remains artificial—as every unit test is—but it is artificial inside the actual language contract.

## Do not assert everything

A test becomes fragile when it records every interaction whether or not that interaction matters to the scenario.

BUNIT allows an expectation to specify only the relevant part of a call. For example:

```basic
"LOG_EVENT _, _" WAS CALLED WITH
    ARGS("INFO", CONTAINS("over limit"))
```

The test requires an informational log message containing `"over limit"`. It does not require the complete message to remain byte-for-byte identical.

Similarly:

```basic
"APPROVE _" WAS NOT CALLED
```

expresses the important negative requirement without inventing an `Order` merely to compare it with another `Order`.

The purpose is not to reproduce the execution trace. It is to state the observable facts that define the business case.

## What this does not test

Opaque tokens do not prove that the Java implementation of `LOAD_ORDER` returns the right order. They do not prove that `ORDER_TOTAL` calculates taxes correctly or that `APPROVE` commits a transaction.

Those operations require their own Java unit and integration tests.

BUNIT tests the program at the orchestration boundary. This makes it possible to test business decisions without databases, service containers or complete domain-object graphs, but it does not replace testing below or beyond that boundary.

Nor does BUNIT make every Java application automatically testable. The application developer first has to expose a suitably designed vocabulary. If one enormous operation performs loading, calculation, approval and notification internally, BUNIT can mock that operation but cannot test the decisions hidden inside it.

Testability therefore provides feedback about vocabulary design. Operations should represent meaningful domain capabilities at the level where business programs genuinely make choices.

## The deeper result

Opaque domain types may initially look like a limitation. The program cannot examine its own values freely. It has to ask the vocabulary to interpret them.

That limitation creates a clean separation:

* Java owns domain representation and implementation.
* BUBAS owns orchestration and decisions.
* BUNIT replaces domain capabilities at that same boundary.
* Tokens replace complex objects with identity when identity is all the test requires.

The production program becomes independent of domain-object structure. The unit test inherits that independence.

We do not need a fake `Order` with a fake customer containing fake line items whose prices happen to add up to `1500.00`.

For this business decision, we need only to say:

```basic
"ORDER_TOTAL" WITH ARGS("o1") RETURNS 1500.00
```

The business program never needed to know what was inside the order.

Neither does its test.
