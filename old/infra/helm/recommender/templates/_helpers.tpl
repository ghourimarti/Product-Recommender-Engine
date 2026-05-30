{{- define "recommender.name" -}}
{{- default "recommender" .Values.nameOverride -}}
{{- end -}}

{{- define "recommender.labels" -}}
app.kubernetes.io/part-of: {{ include "recommender.name" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end -}}

{{- define "recommender.image" -}}
{{- $reg := .Values.image.registry -}}
{{- if $reg -}}{{ $reg }}/{{ .img }}:{{ .tag }}{{- else -}}{{ .img }}:{{ .tag }}{{- end -}}
{{- end -}}
