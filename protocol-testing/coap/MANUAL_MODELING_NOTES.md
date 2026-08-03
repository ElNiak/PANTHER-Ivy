# Personal Impressions and Notes on CoAP Protocol Modeling

## Methodology

- We start by modeling objects and relations that represent the CoAP protocol's structure and behavior.
- We define two simple tests to verify the correctness of the model, ensuring that it accurately reflects the protocol's specifications.
- We define the CoAP message format, including headers, payload, and options, as specified in the CoAP RFC.
- We specify each component individually, ensuring that the model captures the essential features of the protocol.
- We link the components together to form a complete representation of the CoAP message structure.
  - Highlight many manual "errors" when compiling the model (ivy_compile.log errorss), which are not errors in the protocol itself but rather in the modeling process. Errors such as variables not being defined, or types not being properly linked, are common and require careful attention to detail, including understanding the underlying logic of the protocol and how it is represented in the model.
  - many errors are due to syntax issues, such as missing semicolons, capitalization, etc., which can be easily overlooked but have a significant impact on the model's correctness.
  - 