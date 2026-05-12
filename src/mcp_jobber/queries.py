"""GraphQL documents used by the MCP tools.

Kept as module-level constants so they can be introspected and unit tested
without touching the network layer. Fragment reuse minimizes duplication.

VERIFICATION NOTE
-----------------
The pieces below are confirmed against Jobber's public docs / the official
GetJobber app templates: the `EncodedId` scalar, relay-style `nodes` /
`pageInfo` / `totalCount` connections, `clients(first:, after:, filter:
ClientFilterAttributes)`, the `clientEdit` mutation (input `ClientEditInput`,
payload `{ client, userErrors { message path } }`), and `jobs { nodes { id
jobNumber title } }`.

These pieces follow Jobber's documented *conventions* but are NOT verified
against the live schema and may need adjustment per your API version:
  - the `tags` filter field on `ClientFilterAttributes` and the shape of
    `Client.tags`
  - whether `ClientEditInput` accepts a `tags` field (the tag-edit mutation)
  - the `noteCreate` mutation name / input fields, and whether a note can be
    attached to a Quote specifically (`NoteCreateAttributes` was reworked in
    the 2023-08-18 version)
  - `QuoteFilterAttributes` / `InvoiceFilterAttributes` / `JobFilterAttributes`
    field names, and the `quoteStatus` / `invoiceStatus` / `jobStatus` enum
    values
  - whether money lives under `amounts { total }` or a flat `total`
Run `mcp-jobber-introspect` (or paste these into Jobber's GraphiQL) to confirm
and tweak before relying on the write tools in production.
"""

CLIENT_FIELDS = """
fragment ClientFields on Client {
  id
  firstName
  lastName
  companyName
  emails { description primary address }
  phones { description primary number }
  tags { nodes { label } }
  createdAt
  updatedAt
  isArchived
}
"""

QUOTE_FIELDS = """
fragment QuoteFields on Quote {
  id
  quoteNumber
  quoteStatus
  title
  amounts { total subtotal depositAmount }
  client { id firstName lastName companyName }
  createdAt
  updatedAt
}
"""

INVOICE_FIELDS = """
fragment InvoiceFields on Invoice {
  id
  invoiceNumber
  invoiceStatus
  amounts { total paymentsTotal depositAmount }
  dueDate
  issuedDate
  client { id firstName lastName companyName }
  createdAt
  updatedAt
}
"""

JOB_FIELDS = """
fragment JobFields on Job {
  id
  jobNumber
  jobStatus
  title
  startAt
  endAt
  completedAt
  client { id firstName lastName companyName }
  total
  createdAt
  updatedAt
}
"""

LIST_CLIENTS = CLIENT_FIELDS + """
query ListClients($first: Int, $after: String, $filter: ClientFilterAttributes) {
  clients(first: $first, after: $after, filter: $filter) {
    nodes { ...ClientFields }
    pageInfo { hasNextPage endCursor }
    totalCount
  }
}
"""

GET_CLIENT = CLIENT_FIELDS + """
query GetClient($id: EncodedId!) {
  client(id: $id) { ...ClientFields }
}
"""

UPDATE_CLIENT_TAGS = CLIENT_FIELDS + """
mutation UpdateClientTags($id: EncodedId!, $tags: [String!]!) {
  clientEdit(input: { id: $id, tags: $tags }) {
    client { ...ClientFields }
    userErrors { message path }
  }
}
"""

LIST_QUOTES = QUOTE_FIELDS + """
query ListQuotes($first: Int, $filter: QuoteFilterAttributes) {
  quotes(first: $first, filter: $filter) {
    nodes { ...QuoteFields }
    pageInfo { hasNextPage endCursor }
    totalCount
  }
}
"""

GET_QUOTE = QUOTE_FIELDS + """
query GetQuote($id: EncodedId!) {
  quote(id: $id) {
    ...QuoteFields
    lineItems { nodes { name description quantity unitPrice totalPrice } }
    notes { nodes { id message createdAt } }
  }
}
"""

CREATE_NOTE_ON_QUOTE = """
mutation CreateNoteOnQuote($quoteId: EncodedId!, $body: String!) {
  noteCreate(input: { attachedToId: $quoteId, message: $body }) {
    note { id message createdAt }
    userErrors { message path }
  }
}
"""

LIST_INVOICES = INVOICE_FIELDS + """
query ListInvoices($first: Int, $filter: InvoiceFilterAttributes) {
  invoices(first: $first, filter: $filter) {
    nodes { ...InvoiceFields }
    pageInfo { hasNextPage endCursor }
    totalCount
  }
}
"""

LIST_JOBS = JOB_FIELDS + """
query ListJobs($first: Int, $filter: JobFilterAttributes) {
  jobs(first: $first, filter: $filter) {
    nodes { ...JobFields }
    pageInfo { hasNextPage endCursor }
    totalCount
  }
}
"""

SEARCH = """
query GlobalSearch($text: String!, $first: Int) {
  clients(first: $first, searchTerm: $text) {
    nodes { id firstName lastName companyName }
  }
  jobs(first: $first, searchTerm: $text) {
    nodes { id jobNumber title jobStatus }
  }
  quotes(first: $first, searchTerm: $text) {
    nodes { id quoteNumber title quoteStatus }
  }
  invoices(first: $first, searchTerm: $text) {
    nodes { id invoiceNumber invoiceStatus }
  }
}
"""
