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
Pod template labels: the selector labels plus part-of, without the chart and app versions. Any
change to a pod template restarts its pods, so with helm.sh/chart here every chart version bump
would restart every pod, including the single-replica Qdrant and Redis.
*/}}
{{- define "p2.podLabels" -}}
{{ include "p2.selectorLabels" . }}
app.kubernetes.io/part-of: {{ include "p2.name" . }}
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

{{/*
Pod half of the "restricted" Pod Security profile. runAsUser must be numeric: the api and web
images set USER by name (appuser / webuser), and the kubelet won't start a runAsNonRoot pod when
it can't verify that a named user isn't root.

Usage: include "p2.podSecurityContext" .Values.api.securityContext
*/}}
{{- define "p2.podSecurityContext" -}}
runAsNonRoot: true
runAsUser: {{ .runAsUser }}
runAsGroup: {{ .runAsGroup }}
{{- with .fsGroup }}
fsGroup: {{ . }}
{{- end }}
seccompProfile:
  type: RuntimeDefault
{{- end -}}

{{/* Container half of the restricted profile. */}}
{{- define "p2.containerSecurityContext" -}}
allowPrivilegeEscalation: false
readOnlyRootFilesystem: {{ .readOnlyRootFilesystem }}
capabilities:
  drop:
    - ALL
{{- end -}}

{{/*
Spread a Deployment's replicas across nodes. Soft (ScheduleAnyway), so a one-node cluster still
schedules everything. matchLabelKeys keeps the old and new ReplicaSets from being counted
together during a rollout, which would otherwise let new pods pile onto one node.

Usage: include "p2.topologySpread" (dict "root" . "component" "api")
*/}}
{{- define "p2.topologySpread" -}}
- maxSkew: 1
  topologyKey: kubernetes.io/hostname
  whenUnsatisfiable: ScheduleAnyway
  labelSelector:
    matchLabels:
      {{- include "p2.selectorLabels" .root | nindent 6 }}
      app.kubernetes.io/component: {{ .component }}
  matchLabelKeys:
    - pod-template-hash
{{- end -}}
