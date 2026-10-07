{{/*
Names and labels.

Resource names are fixed (api, web, qdrant, redis) so in-cluster URLs like http://qdrant:6333
don't depend on the release name. The trade-off is one release per namespace.
*/}}
{{- define "p2.name" -}}
{{- .Chart.Name -}}
{{- end -}}

{{/*
Selector labels. Deployment and StatefulSet selectors can't be changed after the first install,
so they hold only keys that never change. Each workload adds app.kubernetes.io/component.
*/}}
{{- define "p2.selectorLabels" -}}
app.kubernetes.io/name: {{ include "p2.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{/* Labels for every object: the selector labels plus version and ownership. */}}
{{- define "p2.labels" -}}
{{ include "p2.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/part-of: {{ include "p2.name" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
{{- end -}}

{{/*
Image reference for the images we build (api, web): [registry/]repository:tag.

The tag must be an immutable git SHA. Empty and "latest" are rejected, so a rollout always means
one exact build and a rollback really restores the previous one. It must also be a string:
`--set image.tag=1234567` makes Helm parse an all-digit SHA as a number, so pass tags with
--set-string.

Usage: include "p2.image" (dict "image" .Values.api.image "root" .)
*/}}
{{- define "p2.image" -}}
{{- $tag := .image.tag | default .root.Values.image.tag -}}
{{- if and (not (kindIs "string" $tag)) (not (kindIs "invalid" $tag)) -}}
{{- fail "image.tag must be a string: pass it with --set-string (plain --set turns an all-digit SHA such as 1234567 into a number)" -}}
{{- end -}}
{{- if not $tag -}}
{{- fail "image.tag is required: pass the git SHA with --set-string image.tag=$(git rev-parse --short HEAD)" -}}
{{- end -}}
{{- if eq $tag "latest" -}}
{{- fail "image.tag 'latest' is not allowed: use an immutable git SHA" -}}
{{- end -}}
{{- $registry := .root.Values.image.registry | default "" | trimSuffix "/" -}}
{{- if $registry -}}
{{- printf "%s/%s:%s" $registry .image.repository $tag -}}
{{- else -}}
{{- printf "%s:%s" .image.repository $tag -}}
{{- end -}}
{{- end -}}
