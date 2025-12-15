# Create a response

POST https://openrouter.ai/api/v1/responses
Content-Type: application/json

Creates a streaming or non-streaming response using OpenResponses API format

Reference: https://openrouter.ai/docs/api/api-reference/responses/create-responses

## OpenAPI Specification

```yaml
openapi: 3.1.1
info:
  title: Create a response
  version: endpoint_betaResponses.createResponses
paths:
  /responses:
    post:
      operationId: create-responses
      summary: Create a response
      description: >-
        Creates a streaming or non-streaming response using OpenResponses API
        format
      tags:
        - - subpackage_betaResponses
      parameters:
        - name: Authorization
          in: header
          description: API key as bearer token in Authorization header
          required: true
          schema:
            type: string
      responses:
        '200':
          description: Successful response
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/OpenResponsesNonStreamingResponse'
        '400':
          description: Bad Request - Invalid request parameters or malformed input
          content: {}
        '401':
          description: Unauthorized - Authentication required or invalid credentials
          content: {}
        '402':
          description: Payment Required - Insufficient credits or quota to complete request
          content: {}
        '404':
          description: Not Found - Resource does not exist
          content: {}
        '408':
          description: Request Timeout - Operation exceeded time limit
          content: {}
        '413':
          description: Payload Too Large - Request payload exceeds size limits
          content: {}
        '422':
          description: Unprocessable Entity - Semantic validation failure
          content: {}
        '429':
          description: Too Many Requests - Rate limit exceeded
          content: {}
        '500':
          description: Internal Server Error - Unexpected server error
          content: {}
        '502':
          description: Bad Gateway - Provider/upstream API failure
          content: {}
        '503':
          description: Service Unavailable - Service temporarily unavailable
          content: {}
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/OpenResponsesRequest'
components:
  schemas:
    OutputItemReasoningType:
      type: string
      enum:
        - value: reasoning
    ReasoningTextContentType:
      type: string
      enum:
        - value: reasoning_text
    ReasoningTextContent:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/ReasoningTextContentType'
        text:
          type: string
      required:
        - type
        - text
    ReasoningSummaryTextType:
      type: string
      enum:
        - value: summary_text
    ReasoningSummaryText:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/ReasoningSummaryTextType'
        text:
          type: string
      required:
        - type
        - text
    OutputItemReasoningStatus0:
      type: string
      enum:
        - value: completed
    OutputItemReasoningStatus1:
      type: string
      enum:
        - value: incomplete
    OutputItemReasoningStatus2:
      type: string
      enum:
        - value: in_progress
    OutputItemReasoningStatus:
      oneOf:
        - $ref: '#/components/schemas/OutputItemReasoningStatus0'
        - $ref: '#/components/schemas/OutputItemReasoningStatus1'
        - $ref: '#/components/schemas/OutputItemReasoningStatus2'
    OpenResponsesReasoningFormat:
      type: string
      enum:
        - value: unknown
        - value: openai-responses-v1
        - value: xai-responses-v1
        - value: anthropic-claude-v1
        - value: google-gemini-v1
    OpenResponsesReasoning:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/OutputItemReasoningType'
        id:
          type: string
        content:
          type: array
          items:
            $ref: '#/components/schemas/ReasoningTextContent'
        summary:
          type: array
          items:
            $ref: '#/components/schemas/ReasoningSummaryText'
        encrypted_content:
          type:
            - string
            - 'null'
        status:
          $ref: '#/components/schemas/OutputItemReasoningStatus'
        signature:
          type:
            - string
            - 'null'
        format:
          oneOf:
            - $ref: '#/components/schemas/OpenResponsesReasoningFormat'
            - type: 'null'
      required:
        - type
        - id
        - summary
    OpenResponsesEasyInputMessageType:
      type: string
      enum:
        - value: message
    OpenResponsesEasyInputMessageRole0:
      type: string
      enum:
        - value: user
    OpenResponsesEasyInputMessageRole1:
      type: string
      enum:
        - value: system
    OpenResponsesEasyInputMessageRole2:
      type: string
      enum:
        - value: assistant
    OpenResponsesEasyInputMessageRole3:
      type: string
      enum:
        - value: developer
    OpenResponsesEasyInputMessageRole:
      oneOf:
        - $ref: '#/components/schemas/OpenResponsesEasyInputMessageRole0'
        - $ref: '#/components/schemas/OpenResponsesEasyInputMessageRole1'
        - $ref: '#/components/schemas/OpenResponsesEasyInputMessageRole2'
        - $ref: '#/components/schemas/OpenResponsesEasyInputMessageRole3'
    ResponseInputTextType:
      type: string
      enum:
        - value: input_text
    ResponseInputText:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/ResponseInputTextType'
        text:
          type: string
      required:
        - type
        - text
    ResponseInputImageType:
      type: string
      enum:
        - value: input_image
    ResponseInputImageDetail:
      type: string
      enum:
        - value: auto
        - value: high
        - value: low
    ResponseInputImage:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/ResponseInputImageType'
        detail:
          $ref: '#/components/schemas/ResponseInputImageDetail'
        image_url:
          type:
            - string
            - 'null'
      required:
        - type
        - detail
    ResponseInputFileType:
      type: string
      enum:
        - value: input_file
    ResponseInputFile:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/ResponseInputFileType'
        file_id:
          type:
            - string
            - 'null'
        file_data:
          type: string
        filename:
          type: string
        file_url:
          type: string
      required:
        - type
    ResponseInputAudioType:
      type: string
      enum:
        - value: input_audio
    ResponseInputAudioInputAudioFormat:
      type: string
      enum:
        - value: mp3
        - value: wav
    ResponseInputAudioInputAudio:
      type: object
      properties:
        data:
          type: string
        format:
          $ref: '#/components/schemas/ResponseInputAudioInputAudioFormat'
      required:
        - data
        - format
    ResponseInputAudio:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/ResponseInputAudioType'
        input_audio:
          $ref: '#/components/schemas/ResponseInputAudioInputAudio'
      required:
        - type
        - input_audio
    OpenResponsesEasyInputMessageContentOneOf0Items:
      oneOf:
        - $ref: '#/components/schemas/ResponseInputText'
        - $ref: '#/components/schemas/ResponseInputImage'
        - $ref: '#/components/schemas/ResponseInputFile'
        - $ref: '#/components/schemas/ResponseInputAudio'
    OpenResponsesEasyInputMessageContent0:
      type: array
      items:
        $ref: '#/components/schemas/OpenResponsesEasyInputMessageContentOneOf0Items'
    OpenResponsesEasyInputMessageContent:
      oneOf:
        - $ref: '#/components/schemas/OpenResponsesEasyInputMessageContent0'
        - type: string
    OpenResponsesEasyInputMessage:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/OpenResponsesEasyInputMessageType'
        role:
          $ref: '#/components/schemas/OpenResponsesEasyInputMessageRole'
        content:
          $ref: '#/components/schemas/OpenResponsesEasyInputMessageContent'
      required:
        - role
        - content
    OpenResponsesInputMessageItemType:
      type: string
      enum:
        - value: message
    OpenResponsesInputMessageItemRole0:
      type: string
      enum:
        - value: user
    OpenResponsesInputMessageItemRole1:
      type: string
      enum:
        - value: system
    OpenResponsesInputMessageItemRole2:
      type: string
      enum:
        - value: developer
    OpenResponsesInputMessageItemRole:
      oneOf:
        - $ref: '#/components/schemas/OpenResponsesInputMessageItemRole0'
        - $ref: '#/components/schemas/OpenResponsesInputMessageItemRole1'
        - $ref: '#/components/schemas/OpenResponsesInputMessageItemRole2'
    OpenResponsesInputMessageItemContentItems:
      oneOf:
        - $ref: '#/components/schemas/ResponseInputText'
        - $ref: '#/components/schemas/ResponseInputImage'
        - $ref: '#/components/schemas/ResponseInputFile'
        - $ref: '#/components/schemas/ResponseInputAudio'
    OpenResponsesInputMessageItem:
      type: object
      properties:
        id:
          type: string
        type:
          $ref: '#/components/schemas/OpenResponsesInputMessageItemType'
        role:
          $ref: '#/components/schemas/OpenResponsesInputMessageItemRole'
        content:
          type: array
          items:
            $ref: '#/components/schemas/OpenResponsesInputMessageItemContentItems'
      required:
        - role
        - content
    OpenResponsesFunctionToolCallType:
      type: string
      enum:
        - value: function_call
    ToolCallStatus:
      type: string
      enum:
        - value: in_progress
        - value: completed
        - value: incomplete
    OpenResponsesFunctionToolCall:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/OpenResponsesFunctionToolCallType'
        call_id:
          type: string
        name:
          type: string
        arguments:
          type: string
        id:
          type: string
        status:
          $ref: '#/components/schemas/ToolCallStatus'
      required:
        - type
        - call_id
        - name
        - arguments
        - id
    OpenResponsesFunctionCallOutputType:
      type: string
      enum:
        - value: function_call_output
    OpenResponsesFunctionCallOutput:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/OpenResponsesFunctionCallOutputType'
        id:
          type:
            - string
            - 'null'
        call_id:
          type: string
        output:
          type: string
        status:
          $ref: '#/components/schemas/ToolCallStatus'
      required:
        - type
        - call_id
        - output
    OutputMessageRole:
      type: string
      enum:
        - value: assistant
    OutputMessageType:
      type: string
      enum:
        - value: message
    OutputMessageStatus0:
      type: string
      enum:
        - value: completed
    OutputMessageStatus1:
      type: string
      enum:
        - value: incomplete
    OutputMessageStatus2:
      type: string
      enum:
        - value: in_progress
    OutputMessageStatus:
      oneOf:
        - $ref: '#/components/schemas/OutputMessageStatus0'
        - $ref: '#/components/schemas/OutputMessageStatus1'
        - $ref: '#/components/schemas/OutputMessageStatus2'
    ResponseOutputTextType:
      type: string
      enum:
        - value: output_text
    FileCitationType:
      type: string
      enum:
        - value: file_citation
    FileCitation:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/FileCitationType'
        file_id:
          type: string
        filename:
          type: string
        index:
          type: number
          format: double
      required:
        - type
        - file_id
        - filename
        - index
    UrlCitationType:
      type: string
      enum:
        - value: url_citation
    URLCitation:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/UrlCitationType'
        url:
          type: string
        title:
          type: string
        start_index:
          type: number
          format: double
        end_index:
          type: number
          format: double
      required:
        - type
        - url
        - title
        - start_index
        - end_index
    FilePathType:
      type: string
      enum:
        - value: file_path
    FilePath:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/FilePathType'
        file_id:
          type: string
        index:
          type: number
          format: double
      required:
        - type
        - file_id
        - index
    OpenAIResponsesAnnotation:
      oneOf:
        - $ref: '#/components/schemas/FileCitation'
        - $ref: '#/components/schemas/URLCitation'
        - $ref: '#/components/schemas/FilePath'
    ResponseOutputText:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/ResponseOutputTextType'
        text:
          type: string
        annotations:
          type: array
          items:
            $ref: '#/components/schemas/OpenAIResponsesAnnotation'
      required:
        - type
        - text
    OpenAiResponsesRefusalContentType:
      type: string
      enum:
        - value: refusal
    OpenAIResponsesRefusalContent:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/OpenAiResponsesRefusalContentType'
        refusal:
          type: string
      required:
        - type
        - refusal
    OutputMessageContentItems:
      oneOf:
        - $ref: '#/components/schemas/ResponseOutputText'
        - $ref: '#/components/schemas/OpenAIResponsesRefusalContent'
    ResponsesOutputMessage:
      type: object
      properties:
        id:
          type: string
        role:
          $ref: '#/components/schemas/OutputMessageRole'
        type:
          $ref: '#/components/schemas/OutputMessageType'
        status:
          $ref: '#/components/schemas/OutputMessageStatus'
        content:
          type: array
          items:
            $ref: '#/components/schemas/OutputMessageContentItems'
      required:
        - id
        - role
        - type
        - content
    ResponsesOutputItemReasoning:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/OutputItemReasoningType'
        id:
          type: string
        content:
          type: array
          items:
            $ref: '#/components/schemas/ReasoningTextContent'
        summary:
          type: array
          items:
            $ref: '#/components/schemas/ReasoningSummaryText'
        encrypted_content:
          type:
            - string
            - 'null'
        status:
          $ref: '#/components/schemas/OutputItemReasoningStatus'
      required:
        - type
        - id
        - summary
    OutputItemFunctionCallType:
      type: string
      enum:
        - value: function_call
    OutputItemFunctionCallStatus0:
      type: string
      enum:
        - value: completed
    OutputItemFunctionCallStatus1:
      type: string
      enum:
        - value: incomplete
    OutputItemFunctionCallStatus2:
      type: string
      enum:
        - value: in_progress
    OutputItemFunctionCallStatus:
      oneOf:
        - $ref: '#/components/schemas/OutputItemFunctionCallStatus0'
        - $ref: '#/components/schemas/OutputItemFunctionCallStatus1'
        - $ref: '#/components/schemas/OutputItemFunctionCallStatus2'
    ResponsesOutputItemFunctionCall:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/OutputItemFunctionCallType'
        id:
          type: string
        name:
          type: string
        arguments:
          type: string
        call_id:
          type: string
        status:
          $ref: '#/components/schemas/OutputItemFunctionCallStatus'
      required:
        - type
        - name
        - arguments
        - call_id
    OutputItemWebSearchCallType:
      type: string
      enum:
        - value: web_search_call
    WebSearchStatus:
      type: string
      enum:
        - value: completed
        - value: searching
        - value: in_progress
        - value: failed
    ResponsesWebSearchCallOutput:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/OutputItemWebSearchCallType'
        id:
          type: string
        status:
          $ref: '#/components/schemas/WebSearchStatus'
      required:
        - type
        - id
        - status
    OutputItemFileSearchCallType:
      type: string
      enum:
        - value: file_search_call
    ResponsesOutputItemFileSearchCall:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/OutputItemFileSearchCallType'
        id:
          type: string
        queries:
          type: array
          items:
            type: string
        status:
          $ref: '#/components/schemas/WebSearchStatus'
      required:
        - type
        - id
        - queries
        - status
    OutputItemImageGenerationCallType:
      type: string
      enum:
        - value: image_generation_call
    ImageGenerationStatus:
      type: string
      enum:
        - value: in_progress
        - value: completed
        - value: generating
        - value: failed
    ResponsesImageGenerationCall:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/OutputItemImageGenerationCallType'
        id:
          type: string
        result:
          type:
            - string
            - 'null'
        status:
          $ref: '#/components/schemas/ImageGenerationStatus'
      required:
        - type
        - id
        - status
    OpenResponsesInputOneOf1Items:
      oneOf:
        - $ref: '#/components/schemas/OpenResponsesReasoning'
        - $ref: '#/components/schemas/OpenResponsesEasyInputMessage'
        - $ref: '#/components/schemas/OpenResponsesInputMessageItem'
        - $ref: '#/components/schemas/OpenResponsesFunctionToolCall'
        - $ref: '#/components/schemas/OpenResponsesFunctionCallOutput'
        - $ref: '#/components/schemas/ResponsesOutputMessage'
        - $ref: '#/components/schemas/ResponsesOutputItemReasoning'
        - $ref: '#/components/schemas/ResponsesOutputItemFunctionCall'
        - $ref: '#/components/schemas/ResponsesWebSearchCallOutput'
        - $ref: '#/components/schemas/ResponsesOutputItemFileSearchCall'
        - $ref: '#/components/schemas/ResponsesImageGenerationCall'
    OpenResponsesInput1:
      type: array
      items:
        $ref: '#/components/schemas/OpenResponsesInputOneOf1Items'
    OpenResponsesInput:
      oneOf:
        - type: string
        - $ref: '#/components/schemas/OpenResponsesInput1'
    OpenResponsesRequestMetadata:
      type: object
      additionalProperties:
        type: string
    OpenResponsesWebSearchPreviewToolType:
      type: string
      enum:
        - value: web_search_preview
    ResponsesSearchContextSize:
      type: string
      enum:
        - value: low
        - value: medium
        - value: high
    WebSearchPreviewToolUserLocationType:
      type: string
      enum:
        - value: approximate
    WebSearchPreviewToolUserLocation:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/WebSearchPreviewToolUserLocationType'
        city:
          type:
            - string
            - 'null'
        country:
          type:
            - string
            - 'null'
        region:
          type:
            - string
            - 'null'
        timezone:
          type:
            - string
            - 'null'
      required:
        - type
    OpenResponsesWebSearchPreviewTool:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/OpenResponsesWebSearchPreviewToolType'
        search_context_size:
          $ref: '#/components/schemas/ResponsesSearchContextSize'
        user_location:
          $ref: '#/components/schemas/WebSearchPreviewToolUserLocation'
      required:
        - type
    OpenResponsesWebSearchPreview20250311ToolType:
      type: string
      enum:
        - value: web_search_preview_2025_03_11
    OpenResponsesWebSearchPreview20250311Tool:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/OpenResponsesWebSearchPreview20250311ToolType'
        search_context_size:
          $ref: '#/components/schemas/ResponsesSearchContextSize'
        user_location:
          $ref: '#/components/schemas/WebSearchPreviewToolUserLocation'
      required:
        - type
    OpenResponsesWebSearchToolType:
      type: string
      enum:
        - value: web_search
    OpenResponsesWebSearchToolFilters:
      type: object
      properties:
        allowed_domains:
          type:
            - array
            - 'null'
          items:
            type: string
    ResponsesWebSearchUserLocationType:
      type: string
      enum:
        - value: approximate
    ResponsesWebSearchUserLocation:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/ResponsesWebSearchUserLocationType'
        city:
          type:
            - string
            - 'null'
        country:
          type:
            - string
            - 'null'
        region:
          type:
            - string
            - 'null'
        timezone:
          type:
            - string
            - 'null'
    OpenResponsesWebSearchTool:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/OpenResponsesWebSearchToolType'
        filters:
          oneOf:
            - $ref: '#/components/schemas/OpenResponsesWebSearchToolFilters'
            - type: 'null'
        search_context_size:
          $ref: '#/components/schemas/ResponsesSearchContextSize'
        user_location:
          $ref: '#/components/schemas/ResponsesWebSearchUserLocation'
      required:
        - type
    OpenResponsesWebSearch20250826ToolType:
      type: string
      enum:
        - value: web_search_2025_08_26
    OpenResponsesWebSearch20250826ToolFilters:
      type: object
      properties:
        allowed_domains:
          type:
            - array
            - 'null'
          items:
            type: string
    OpenResponsesWebSearch20250826Tool:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/OpenResponsesWebSearch20250826ToolType'
        filters:
          oneOf:
            - $ref: '#/components/schemas/OpenResponsesWebSearch20250826ToolFilters'
            - type: 'null'
        search_context_size:
          $ref: '#/components/schemas/ResponsesSearchContextSize'
        user_location:
          $ref: '#/components/schemas/ResponsesWebSearchUserLocation'
      required:
        - type
    OpenResponsesRequestToolsItems:
      oneOf:
        - type: object
          additionalProperties:
            description: Any type
        - $ref: '#/components/schemas/OpenResponsesWebSearchPreviewTool'
        - $ref: '#/components/schemas/OpenResponsesWebSearchPreview20250311Tool'
        - $ref: '#/components/schemas/OpenResponsesWebSearchTool'
        - $ref: '#/components/schemas/OpenResponsesWebSearch20250826Tool'
    OpenAiResponsesToolChoice0:
      type: string
      enum:
        - value: auto
    OpenAiResponsesToolChoice1:
      type: string
      enum:
        - value: none
    OpenAiResponsesToolChoice2:
      type: string
      enum:
        - value: required
    OpenAiResponsesToolChoiceOneOf3Type:
      type: string
      enum:
        - value: function
    OpenAiResponsesToolChoice3:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/OpenAiResponsesToolChoiceOneOf3Type'
        name:
          type: string
      required:
        - type
        - name
    OpenAiResponsesToolChoiceOneOf4Type0:
      type: string
      enum:
        - value: web_search_preview_2025_03_11
    OpenAiResponsesToolChoiceOneOf4Type1:
      type: string
      enum:
        - value: web_search_preview
    OpenAiResponsesToolChoiceOneOf4Type:
      oneOf:
        - $ref: '#/components/schemas/OpenAiResponsesToolChoiceOneOf4Type0'
        - $ref: '#/components/schemas/OpenAiResponsesToolChoiceOneOf4Type1'
    OpenAiResponsesToolChoice4:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/OpenAiResponsesToolChoiceOneOf4Type'
      required:
        - type
    OpenAIResponsesToolChoice:
      oneOf:
        - $ref: '#/components/schemas/OpenAiResponsesToolChoice0'
        - $ref: '#/components/schemas/OpenAiResponsesToolChoice1'
        - $ref: '#/components/schemas/OpenAiResponsesToolChoice2'
        - $ref: '#/components/schemas/OpenAiResponsesToolChoice3'
        - $ref: '#/components/schemas/OpenAiResponsesToolChoice4'
    ResponsesFormatTextType:
      type: string
      enum:
        - value: text
    ResponsesFormatText:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/ResponsesFormatTextType'
      required:
        - type
    ResponsesFormatJsonObjectType:
      type: string
      enum:
        - value: json_object
    ResponsesFormatJSONObject:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/ResponsesFormatJsonObjectType'
      required:
        - type
    ResponsesFormatTextJsonSchemaConfigType:
      type: string
      enum:
        - value: json_schema
    ResponsesFormatTextJSONSchemaConfig:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/ResponsesFormatTextJsonSchemaConfigType'
        name:
          type: string
        description:
          type: string
        strict:
          type:
            - boolean
            - 'null'
        schema:
          type: object
          additionalProperties:
            description: Any type
      required:
        - type
        - name
        - schema
    ResponseFormatTextConfig:
      oneOf:
        - $ref: '#/components/schemas/ResponsesFormatText'
        - $ref: '#/components/schemas/ResponsesFormatJSONObject'
        - $ref: '#/components/schemas/ResponsesFormatTextJSONSchemaConfig'
    ResponseTextConfigVerbosity:
      type: string
      enum:
        - value: high
        - value: low
        - value: medium
    OpenResponsesResponseText:
      type: object
      properties:
        format:
          $ref: '#/components/schemas/ResponseFormatTextConfig'
        verbosity:
          oneOf:
            - $ref: '#/components/schemas/ResponseTextConfigVerbosity'
            - type: 'null'
    OpenAIResponsesReasoningEffort:
      type: string
      enum:
        - value: xhigh
        - value: high
        - value: medium
        - value: low
        - value: minimal
        - value: none
    ReasoningSummaryVerbosity:
      type: string
      enum:
        - value: auto
        - value: concise
        - value: detailed
    OpenResponsesReasoningConfig:
      type: object
      properties:
        effort:
          $ref: '#/components/schemas/OpenAIResponsesReasoningEffort'
        summary:
          $ref: '#/components/schemas/ReasoningSummaryVerbosity'
        max_tokens:
          type:
            - number
            - 'null'
          format: double
        enabled:
          type:
            - boolean
            - 'null'
    OpenAiResponsesPromptVariables:
      oneOf:
        - type: string
        - $ref: '#/components/schemas/ResponseInputText'
        - $ref: '#/components/schemas/ResponseInputImage'
        - $ref: '#/components/schemas/ResponseInputFile'
    OpenAIResponsesPrompt:
      type: object
      properties:
        id:
          type: string
        variables:
          type:
            - object
            - 'null'
          additionalProperties:
            $ref: '#/components/schemas/OpenAiResponsesPromptVariables'
      required:
        - id
    OpenAIResponsesIncludable:
      type: string
      enum:
        - value: file_search_call.results
        - value: message.input_image.image_url
        - value: computer_call_output.output.image_url
        - value: reasoning.encrypted_content
        - value: code_interpreter_call.outputs
    OpenResponsesRequestServiceTier:
      type: string
      enum:
        - value: auto
    OpenResponsesRequestTruncation:
      type: object
      properties: {}
    DataCollection:
      type: string
      enum:
        - value: deny
        - value: allow
    ProviderName:
      type: string
      enum:
        - value: AI21
        - value: AionLabs
        - value: Alibaba
        - value: Amazon Bedrock
        - value: Amazon Nova
        - value: Anthropic
        - value: Arcee AI
        - value: AtlasCloud
        - value: Avian
        - value: Azure
        - value: BaseTen
        - value: BytePlus
        - value: Black Forest Labs
        - value: Cerebras
        - value: Chutes
        - value: Cirrascale
        - value: Clarifai
        - value: Cloudflare
        - value: Cohere
        - value: Crusoe
        - value: DeepInfra
        - value: DeepSeek
        - value: Featherless
        - value: Fireworks
        - value: Friendli
        - value: GMICloud
        - value: GoPomelo
        - value: Google
        - value: Google AI Studio
        - value: Groq
        - value: Hyperbolic
        - value: Inception
        - value: InferenceNet
        - value: Infermatic
        - value: Inflection
        - value: Liquid
        - value: Mara
        - value: Mancer 2
        - value: Minimax
        - value: ModelRun
        - value: Mistral
        - value: Modular
        - value: Moonshot AI
        - value: Morph
        - value: NCompass
        - value: Nebius
        - value: NextBit
        - value: Novita
        - value: Nvidia
        - value: OpenAI
        - value: OpenInference
        - value: Parasail
        - value: Perplexity
        - value: Phala
        - value: Relace
        - value: SambaNova
        - value: SiliconFlow
        - value: Sourceful
        - value: Stealth
        - value: StreamLake
        - value: Switchpoint
        - value: Targon
        - value: Together
        - value: Venice
        - value: WandB
        - value: Xiaomi
        - value: xAI
        - value: Z.AI
        - value: FakeProvider
    OpenResponsesRequestProviderOrderItems:
      oneOf:
        - $ref: '#/components/schemas/ProviderName'
        - type: string
    OpenResponsesRequestProviderOnlyItems:
      oneOf:
        - $ref: '#/components/schemas/ProviderName'
        - type: string
    OpenResponsesRequestProviderIgnoreItems:
      oneOf:
        - $ref: '#/components/schemas/ProviderName'
        - type: string
    Quantization:
      type: string
      enum:
        - value: int4
        - value: int8
        - value: fp4
        - value: fp6
        - value: fp8
        - value: fp16
        - value: bf16
        - value: fp32
        - value: unknown
    ProviderSort:
      type: string
      enum:
        - value: price
        - value: throughput
        - value: latency
    BigNumberUnion:
      type: string
    OpenResponsesRequestProviderMaxPrice:
      type: object
      properties:
        prompt:
          $ref: '#/components/schemas/BigNumberUnion'
        completion:
          $ref: '#/components/schemas/BigNumberUnion'
        image:
          $ref: '#/components/schemas/BigNumberUnion'
        audio:
          $ref: '#/components/schemas/BigNumberUnion'
        request:
          $ref: '#/components/schemas/BigNumberUnion'
    OpenResponsesRequestProvider:
      type: object
      properties:
        allow_fallbacks:
          type:
            - boolean
            - 'null'
        require_parameters:
          type:
            - boolean
            - 'null'
        data_collection:
          $ref: '#/components/schemas/DataCollection'
        zdr:
          type:
            - boolean
            - 'null'
        enforce_distillable_text:
          type:
            - boolean
            - 'null'
        order:
          type:
            - array
            - 'null'
          items:
            $ref: '#/components/schemas/OpenResponsesRequestProviderOrderItems'
        only:
          type:
            - array
            - 'null'
          items:
            $ref: '#/components/schemas/OpenResponsesRequestProviderOnlyItems'
        ignore:
          type:
            - array
            - 'null'
          items:
            $ref: '#/components/schemas/OpenResponsesRequestProviderIgnoreItems'
        quantizations:
          type:
            - array
            - 'null'
          items:
            $ref: '#/components/schemas/Quantization'
        sort:
          $ref: '#/components/schemas/ProviderSort'
        max_price:
          $ref: '#/components/schemas/OpenResponsesRequestProviderMaxPrice'
        min_throughput:
          type:
            - number
            - 'null'
          format: double
        max_latency:
          type:
            - number
            - 'null'
          format: double
    OpenResponsesRequestPluginsItemsOneOf0Id:
      type: string
      enum:
        - value: moderation
    OpenResponsesRequestPluginsItems0:
      type: object
      properties:
        id:
          $ref: '#/components/schemas/OpenResponsesRequestPluginsItemsOneOf0Id'
      required:
        - id
    OpenResponsesRequestPluginsItemsOneOf1Id:
      type: string
      enum:
        - value: web
    OpenResponsesRequestPluginsItemsOneOf1Engine:
      type: string
      enum:
        - value: native
        - value: exa
    OpenResponsesRequestPluginsItems1:
      type: object
      properties:
        id:
          $ref: '#/components/schemas/OpenResponsesRequestPluginsItemsOneOf1Id'
        enabled:
          type: boolean
        max_results:
          type: number
          format: double
        search_prompt:
          type: string
        engine:
          $ref: '#/components/schemas/OpenResponsesRequestPluginsItemsOneOf1Engine'
      required:
        - id
    OpenResponsesRequestPluginsItemsOneOf2Id:
      type: string
      enum:
        - value: file-parser
    OpenResponsesRequestPluginsItemsOneOf2PdfEngine:
      type: string
      enum:
        - value: mistral-ocr
        - value: pdf-text
        - value: native
    OpenResponsesRequestPluginsItemsOneOf2Pdf:
      type: object
      properties:
        engine:
          $ref: '#/components/schemas/OpenResponsesRequestPluginsItemsOneOf2PdfEngine'
    OpenResponsesRequestPluginsItems2:
      type: object
      properties:
        id:
          $ref: '#/components/schemas/OpenResponsesRequestPluginsItemsOneOf2Id'
        enabled:
          type: boolean
        pdf:
          $ref: '#/components/schemas/OpenResponsesRequestPluginsItemsOneOf2Pdf'
      required:
        - id
    OpenResponsesRequestPluginsItemsOneOf3Id:
      type: string
      enum:
        - value: response-healing
    OpenResponsesRequestPluginsItems3:
      type: object
      properties:
        id:
          $ref: '#/components/schemas/OpenResponsesRequestPluginsItemsOneOf3Id'
        enabled:
          type: boolean
      required:
        - id
    OpenResponsesRequestPluginsItems:
      oneOf:
        - $ref: '#/components/schemas/OpenResponsesRequestPluginsItems0'
        - $ref: '#/components/schemas/OpenResponsesRequestPluginsItems1'
        - $ref: '#/components/schemas/OpenResponsesRequestPluginsItems2'
        - $ref: '#/components/schemas/OpenResponsesRequestPluginsItems3'
    OpenResponsesRequestRoute:
      type: string
      enum:
        - value: fallback
        - value: sort
    OpenResponsesRequest:
      type: object
      properties:
        input:
          $ref: '#/components/schemas/OpenResponsesInput'
        instructions:
          type:
            - string
            - 'null'
        metadata:
          $ref: '#/components/schemas/OpenResponsesRequestMetadata'
        tools:
          type: array
          items:
            $ref: '#/components/schemas/OpenResponsesRequestToolsItems'
        tool_choice:
          $ref: '#/components/schemas/OpenAIResponsesToolChoice'
        parallel_tool_calls:
          type:
            - boolean
            - 'null'
        model:
          type: string
        models:
          type: array
          items:
            type: string
        text:
          $ref: '#/components/schemas/OpenResponsesResponseText'
        reasoning:
          $ref: '#/components/schemas/OpenResponsesReasoningConfig'
        max_output_tokens:
          type:
            - number
            - 'null'
          format: double
        temperature:
          type:
            - number
            - 'null'
          format: double
        top_p:
          type:
            - number
            - 'null'
          format: double
        top_k:
          type: number
          format: double
        prompt_cache_key:
          type:
            - string
            - 'null'
        previous_response_id:
          type:
            - string
            - 'null'
        prompt:
          $ref: '#/components/schemas/OpenAIResponsesPrompt'
        include:
          type:
            - array
            - 'null'
          items:
            $ref: '#/components/schemas/OpenAIResponsesIncludable'
        background:
          type:
            - boolean
            - 'null'
        safety_identifier:
          type:
            - string
            - 'null'
        store:
          type: string
          enum:
            - type: booleanLiteral
              value: false
        service_tier:
          $ref: '#/components/schemas/OpenResponsesRequestServiceTier'
        truncation:
          $ref: '#/components/schemas/OpenResponsesRequestTruncation'
        stream:
          type: boolean
        provider:
          oneOf:
            - $ref: '#/components/schemas/OpenResponsesRequestProvider'
            - type: 'null'
        plugins:
          type: array
          items:
            $ref: '#/components/schemas/OpenResponsesRequestPluginsItems'
        route:
          oneOf:
            - $ref: '#/components/schemas/OpenResponsesRequestRoute'
            - type: 'null'
        user:
          type: string
        session_id:
          type: string
    OpenAiResponsesNonStreamingResponseObject:
      type: string
      enum:
        - value: response
    OpenAIResponsesResponseStatus:
      type: string
      enum:
        - value: completed
        - value: incomplete
        - value: in_progress
        - value: failed
        - value: cancelled
        - value: queued
    OutputMessage:
      type: object
      properties:
        id:
          type: string
        role:
          $ref: '#/components/schemas/OutputMessageRole'
        type:
          $ref: '#/components/schemas/OutputMessageType'
        status:
          $ref: '#/components/schemas/OutputMessageStatus'
        content:
          type: array
          items:
            $ref: '#/components/schemas/OutputMessageContentItems'
      required:
        - id
        - role
        - type
        - content
    OutputItemReasoning:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/OutputItemReasoningType'
        id:
          type: string
        content:
          type: array
          items:
            $ref: '#/components/schemas/ReasoningTextContent'
        summary:
          type: array
          items:
            $ref: '#/components/schemas/ReasoningSummaryText'
        encrypted_content:
          type:
            - string
            - 'null'
        status:
          $ref: '#/components/schemas/OutputItemReasoningStatus'
      required:
        - type
        - id
        - summary
    OutputItemFunctionCall:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/OutputItemFunctionCallType'
        id:
          type: string
        name:
          type: string
        arguments:
          type: string
        call_id:
          type: string
        status:
          $ref: '#/components/schemas/OutputItemFunctionCallStatus'
      required:
        - type
        - name
        - arguments
        - call_id
    OutputItemWebSearchCall:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/OutputItemWebSearchCallType'
        id:
          type: string
        status:
          $ref: '#/components/schemas/WebSearchStatus'
      required:
        - type
        - id
        - status
    OutputItemFileSearchCall:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/OutputItemFileSearchCallType'
        id:
          type: string
        queries:
          type: array
          items:
            type: string
        status:
          $ref: '#/components/schemas/WebSearchStatus'
      required:
        - type
        - id
        - queries
        - status
    OutputItemImageGenerationCall:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/OutputItemImageGenerationCallType'
        id:
          type: string
        result:
          type:
            - string
            - 'null'
        status:
          $ref: '#/components/schemas/ImageGenerationStatus'
      required:
        - type
        - id
        - status
    OpenAiResponsesNonStreamingResponseOutputItems:
      oneOf:
        - $ref: '#/components/schemas/OutputMessage'
        - $ref: '#/components/schemas/OutputItemReasoning'
        - $ref: '#/components/schemas/OutputItemFunctionCall'
        - $ref: '#/components/schemas/OutputItemWebSearchCall'
        - $ref: '#/components/schemas/OutputItemFileSearchCall'
        - $ref: '#/components/schemas/OutputItemImageGenerationCall'
    ResponsesErrorFieldCode:
      type: string
      enum:
        - value: server_error
        - value: rate_limit_exceeded
        - value: invalid_prompt
        - value: vector_store_timeout
        - value: invalid_image
        - value: invalid_image_format
        - value: invalid_base64_image
        - value: invalid_image_url
        - value: image_too_large
        - value: image_too_small
        - value: image_parse_error
        - value: image_content_policy_violation
        - value: invalid_image_mode
        - value: image_file_too_large
        - value: unsupported_image_media_type
        - value: empty_image_file
        - value: failed_to_download_image
        - value: image_file_not_found
    ResponsesErrorField:
      type: object
      properties:
        code:
          $ref: '#/components/schemas/ResponsesErrorFieldCode'
        message:
          type: string
      required:
        - code
        - message
    OpenAiResponsesIncompleteDetailsReason:
      type: string
      enum:
        - value: max_output_tokens
        - value: content_filter
    OpenAIResponsesIncompleteDetails:
      type: object
      properties:
        reason:
          $ref: '#/components/schemas/OpenAiResponsesIncompleteDetailsReason'
    OpenAiResponsesUsageInputTokensDetails:
      type: object
      properties:
        cached_tokens:
          type: number
          format: double
      required:
        - cached_tokens
    OpenAiResponsesUsageOutputTokensDetails:
      type: object
      properties:
        reasoning_tokens:
          type: number
          format: double
      required:
        - reasoning_tokens
    OpenAIResponsesUsage:
      type: object
      properties:
        input_tokens:
          type: number
          format: double
        input_tokens_details:
          $ref: '#/components/schemas/OpenAiResponsesUsageInputTokensDetails'
        output_tokens:
          type: number
          format: double
        output_tokens_details:
          $ref: '#/components/schemas/OpenAiResponsesUsageOutputTokensDetails'
        total_tokens:
          type: number
          format: double
      required:
        - input_tokens
        - input_tokens_details
        - output_tokens
        - output_tokens_details
        - total_tokens
    OpenAiResponsesInputOneOf1ItemsOneOf0Type:
      type: string
      enum:
        - value: message
    OpenAiResponsesInputOneOf1ItemsOneOf0Role0:
      type: string
      enum:
        - value: user
    OpenAiResponsesInputOneOf1ItemsOneOf0Role1:
      type: string
      enum:
        - value: system
    OpenAiResponsesInputOneOf1ItemsOneOf0Role2:
      type: string
      enum:
        - value: assistant
    OpenAiResponsesInputOneOf1ItemsOneOf0Role3:
      type: string
      enum:
        - value: developer
    OpenAiResponsesInputOneOf1ItemsOneOf0Role:
      oneOf:
        - $ref: '#/components/schemas/OpenAiResponsesInputOneOf1ItemsOneOf0Role0'
        - $ref: '#/components/schemas/OpenAiResponsesInputOneOf1ItemsOneOf0Role1'
        - $ref: '#/components/schemas/OpenAiResponsesInputOneOf1ItemsOneOf0Role2'
        - $ref: '#/components/schemas/OpenAiResponsesInputOneOf1ItemsOneOf0Role3'
    OpenAiResponsesInputOneOf1ItemsOneOf0ContentOneOf0Items:
      oneOf:
        - $ref: '#/components/schemas/ResponseInputText'
        - $ref: '#/components/schemas/ResponseInputImage'
        - $ref: '#/components/schemas/ResponseInputFile'
        - $ref: '#/components/schemas/ResponseInputAudio'
    OpenAiResponsesInputOneOf1ItemsOneOf0Content0:
      type: array
      items:
        $ref: >-
          #/components/schemas/OpenAiResponsesInputOneOf1ItemsOneOf0ContentOneOf0Items
    OpenAiResponsesInputOneOf1ItemsOneOf0Content:
      oneOf:
        - $ref: '#/components/schemas/OpenAiResponsesInputOneOf1ItemsOneOf0Content0'
        - type: string
    OpenAiResponsesInputOneOf1Items0:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/OpenAiResponsesInputOneOf1ItemsOneOf0Type'
        role:
          $ref: '#/components/schemas/OpenAiResponsesInputOneOf1ItemsOneOf0Role'
        content:
          $ref: '#/components/schemas/OpenAiResponsesInputOneOf1ItemsOneOf0Content'
      required:
        - role
        - content
    OpenAiResponsesInputOneOf1ItemsOneOf1Type:
      type: string
      enum:
        - value: message
    OpenAiResponsesInputOneOf1ItemsOneOf1Role0:
      type: string
      enum:
        - value: user
    OpenAiResponsesInputOneOf1ItemsOneOf1Role1:
      type: string
      enum:
        - value: system
    OpenAiResponsesInputOneOf1ItemsOneOf1Role2:
      type: string
      enum:
        - value: developer
    OpenAiResponsesInputOneOf1ItemsOneOf1Role:
      oneOf:
        - $ref: '#/components/schemas/OpenAiResponsesInputOneOf1ItemsOneOf1Role0'
        - $ref: '#/components/schemas/OpenAiResponsesInputOneOf1ItemsOneOf1Role1'
        - $ref: '#/components/schemas/OpenAiResponsesInputOneOf1ItemsOneOf1Role2'
    OpenAiResponsesInputOneOf1ItemsOneOf1ContentItems:
      oneOf:
        - $ref: '#/components/schemas/ResponseInputText'
        - $ref: '#/components/schemas/ResponseInputImage'
        - $ref: '#/components/schemas/ResponseInputFile'
        - $ref: '#/components/schemas/ResponseInputAudio'
    OpenAiResponsesInputOneOf1Items1:
      type: object
      properties:
        id:
          type: string
        type:
          $ref: '#/components/schemas/OpenAiResponsesInputOneOf1ItemsOneOf1Type'
        role:
          $ref: '#/components/schemas/OpenAiResponsesInputOneOf1ItemsOneOf1Role'
        content:
          type: array
          items:
            $ref: >-
              #/components/schemas/OpenAiResponsesInputOneOf1ItemsOneOf1ContentItems
      required:
        - id
        - role
        - content
    OpenAiResponsesInputOneOf1ItemsOneOf2Type:
      type: string
      enum:
        - value: function_call_output
    OpenAiResponsesInputOneOf1Items2:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/OpenAiResponsesInputOneOf1ItemsOneOf2Type'
        id:
          type:
            - string
            - 'null'
        call_id:
          type: string
        output:
          type: string
        status:
          $ref: '#/components/schemas/ToolCallStatus'
      required:
        - type
        - call_id
        - output
    OpenAiResponsesInputOneOf1ItemsOneOf3Type:
      type: string
      enum:
        - value: function_call
    OpenAiResponsesInputOneOf1Items3:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/OpenAiResponsesInputOneOf1ItemsOneOf3Type'
        call_id:
          type: string
        name:
          type: string
        arguments:
          type: string
        id:
          type: string
        status:
          $ref: '#/components/schemas/ToolCallStatus'
      required:
        - type
        - call_id
        - name
        - arguments
    OpenAiResponsesInputOneOf1Items:
      oneOf:
        - $ref: '#/components/schemas/OpenAiResponsesInputOneOf1Items0'
        - $ref: '#/components/schemas/OpenAiResponsesInputOneOf1Items1'
        - $ref: '#/components/schemas/OpenAiResponsesInputOneOf1Items2'
        - $ref: '#/components/schemas/OpenAiResponsesInputOneOf1Items3'
        - $ref: '#/components/schemas/OutputItemImageGenerationCall'
        - $ref: '#/components/schemas/OutputMessage'
    OpenAiResponsesInput1:
      type: array
      items:
        $ref: '#/components/schemas/OpenAiResponsesInputOneOf1Items'
    OpenAIResponsesInput:
      oneOf:
        - type: string
        - $ref: '#/components/schemas/OpenAiResponsesInput1'
        - description: Any type
    OpenAiResponsesNonStreamingResponseToolsItems:
      oneOf:
        - type: object
          additionalProperties:
            description: Any type
        - $ref: '#/components/schemas/OpenResponsesWebSearchPreviewTool'
        - $ref: '#/components/schemas/OpenResponsesWebSearchPreview20250311Tool'
        - $ref: '#/components/schemas/OpenResponsesWebSearchTool'
        - $ref: '#/components/schemas/OpenResponsesWebSearch20250826Tool'
    OpenAIResponsesReasoningConfig:
      type: object
      properties:
        effort:
          $ref: '#/components/schemas/OpenAIResponsesReasoningEffort'
        summary:
          $ref: '#/components/schemas/ReasoningSummaryVerbosity'
    OpenAIResponsesServiceTier:
      type: string
      enum:
        - value: auto
        - value: default
        - value: flex
        - value: priority
        - value: scale
    OpenAIResponsesTruncation:
      type: string
      enum:
        - value: auto
        - value: disabled
    ResponseTextConfig:
      type: object
      properties:
        format:
          $ref: '#/components/schemas/ResponseFormatTextConfig'
        verbosity:
          oneOf:
            - $ref: '#/components/schemas/ResponseTextConfigVerbosity'
            - type: 'null'
    ResponsesOutputItem:
      oneOf:
        - $ref: '#/components/schemas/ResponsesOutputMessage'
        - $ref: '#/components/schemas/ResponsesOutputItemReasoning'
        - $ref: '#/components/schemas/ResponsesOutputItemFunctionCall'
        - $ref: '#/components/schemas/ResponsesWebSearchCallOutput'
        - $ref: '#/components/schemas/ResponsesOutputItemFileSearchCall'
        - $ref: '#/components/schemas/ResponsesImageGenerationCall'
    OpenResponsesUsageCostDetails:
      type: object
      properties:
        upstream_inference_cost:
          type:
            - number
            - 'null'
          format: double
        upstream_inference_input_cost:
          type: number
          format: double
        upstream_inference_output_cost:
          type: number
          format: double
      required:
        - upstream_inference_input_cost
        - upstream_inference_output_cost
    OpenResponsesUsage:
      type: object
      properties:
        input_tokens:
          type: number
          format: double
        input_tokens_details:
          $ref: '#/components/schemas/OpenAiResponsesUsageInputTokensDetails'
        output_tokens:
          type: number
          format: double
        output_tokens_details:
          $ref: '#/components/schemas/OpenAiResponsesUsageOutputTokensDetails'
        total_tokens:
          type: number
          format: double
        cost:
          type:
            - number
            - 'null'
          format: double
        is_byok:
          type: boolean
        cost_details:
          $ref: '#/components/schemas/OpenResponsesUsageCostDetails'
      required:
        - input_tokens
        - input_tokens_details
        - output_tokens
        - output_tokens_details
        - total_tokens
    OpenResponsesNonStreamingResponse:
      type: object
      properties:
        id:
          type: string
        object:
          $ref: '#/components/schemas/OpenAiResponsesNonStreamingResponseObject'
        created_at:
          type: number
          format: double
        model:
          type: string
        status:
          $ref: '#/components/schemas/OpenAIResponsesResponseStatus'
        output:
          type: array
          items:
            $ref: '#/components/schemas/ResponsesOutputItem'
        user:
          type:
            - string
            - 'null'
        output_text:
          type: string
        prompt_cache_key:
          type:
            - string
            - 'null'
        safety_identifier:
          type:
            - string
            - 'null'
        error:
          $ref: '#/components/schemas/ResponsesErrorField'
        incomplete_details:
          $ref: '#/components/schemas/OpenAIResponsesIncompleteDetails'
        usage:
          $ref: '#/components/schemas/OpenResponsesUsage'
        max_tool_calls:
          type:
            - number
            - 'null'
          format: double
        top_logprobs:
          type: number
          format: double
        max_output_tokens:
          type:
            - number
            - 'null'
          format: double
        temperature:
          type:
            - number
            - 'null'
          format: double
        top_p:
          type:
            - number
            - 'null'
          format: double
        instructions:
          $ref: '#/components/schemas/OpenAIResponsesInput'
        metadata:
          $ref: '#/components/schemas/OpenResponsesRequestMetadata'
        tools:
          type: array
          items:
            $ref: '#/components/schemas/OpenAiResponsesNonStreamingResponseToolsItems'
        tool_choice:
          $ref: '#/components/schemas/OpenAIResponsesToolChoice'
        parallel_tool_calls:
          type: boolean
        prompt:
          $ref: '#/components/schemas/OpenAIResponsesPrompt'
        background:
          type:
            - boolean
            - 'null'
        previous_response_id:
          type:
            - string
            - 'null'
        reasoning:
          $ref: '#/components/schemas/OpenAIResponsesReasoningConfig'
        service_tier:
          $ref: '#/components/schemas/OpenAIResponsesServiceTier'
        store:
          type: boolean
        truncation:
          $ref: '#/components/schemas/OpenAIResponsesTruncation'
        text:
          $ref: '#/components/schemas/ResponseTextConfig'
      required:
        - id
        - object
        - created_at
        - model
        - output
        - error
        - incomplete_details
        - temperature
        - top_p
        - instructions
        - metadata
        - tools
        - tool_choice
        - parallel_tool_calls

```

## SDK Code Examples

```python
import requests

url = "https://openrouter.ai/api/v1/responses"

payload = {
    "input": [
        {
            "type": "message",
            "role": "user",
            "content": "Hello, how are you?"
        }
    ],
    "tools": [
        {
            "type": "function",
            "name": "get_current_weather",
            "description": "Get the current weather in a given location",
            "parameters": {
                "type": "object",
                "properties": { "location": { "type": "string" } }
            }
        }
    ],
    "model": "anthropic/claude-4.5-sonnet-20250929",
    "temperature": 0.7,
    "top_p": 0.9
}
headers = {
    "Authorization": "Bearer <token>",
    "Content-Type": "application/json"
}

response = requests.post(url, json=payload, headers=headers)

print(response.json())
```

### 200 Successful
```json
{
  "created_at": 1704067200,
  "error": {},
  "id": "resp-abc123",
  "incomplete_details": {},
  "instructions": {},
  "metadata": {},
  "model": "gpt-4",
  "object": "response",
  "parallel_tool_calls": true,
  "temperature": {},
  "tool_choice": "auto",
  "tools": [],
  "top_p": {},
  "max_output_tokens": {},
  "output": [
    {
      "id": "msg-abc123",
      "role": "assistant",
      "type": "message",
      "status": "completed",
      "content": [
        {
          "type": "output_text",
          "text": "Hello! How can I help you today?",
          "annotations": []
        }
      ]
    }
  ],
  "status": "completed",
  "usage": {
    "input_tokens": 10,
    "input_tokens_details": {
      "cached_tokens": 0
    },
    "output_tokens": 25,
    "output_tokens_details": {
      "reasoning_tokens": 0
    },
    "total_tokens": 35
  }
}
```