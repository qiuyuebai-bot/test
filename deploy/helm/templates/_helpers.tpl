{{/*
Expand the name of the chart.
*/}}
{{- define "knowledge-system.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this
(by the DNS naming spec).
*/}}
{{- define "knowledge-system.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "knowledge-system.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Common labels applied to all resources.
*/}}
{{- define "knowledge-system.labels" -}}
helm.sh/chart: {{ include "knowledge-system.chart" . }}
{{ include "knowledge-system.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: knowledge-system
{{- end -}}

{{/*
Selector labels (subset of labels, must be stable across upgrades).
*/}}
{{- define "knowledge-system.selectorLabels" -}}
app.kubernetes.io/name: {{ include "knowledge-system.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{/*
Service account name.
*/}}
{{- define "knowledge-system.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "knowledge-system.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}

{{/*
Image reference: registry/repository:tag with pull policy.
Usage: {{ include "knowledge-system.image" (list .Values.images.backend .Values.global) }}
*/}}
{{- define "knowledge-system.image" -}}
{{- $img := index . 0 -}}
{{- $global := index . 1 -}}
{{- $registry := $global.imageRegistry -}}
{{- if $registry -}}
{{- printf "%s/%s:%s" $registry $img.repository $img.tag -}}
{{- else -}}
{{- printf "%s:%s" $img.repository $img.tag -}}
{{- end -}}
{{- end -}}

{{/*
Backend ConfigMap name.
*/}}
{{- define "knowledge-system.configMapName" -}}
{{- include "knowledge-system.fullname" . }}-config
{{- end -}}

{{/*
Backend Secret name (respect existing secret override).
*/}}
{{- define "knowledge-system.secretName" -}}
{{- if .Values.secrets.existingSecret -}}
{{- .Values.secrets.existingSecret -}}
{{- else -}}
{{- include "knowledge-system.fullname" . }}-secret
{{- end -}}
{{- end -}}

{{/*
PostgreSQL service name (used by both postgres StatefulSet and backend env).
*/}}
{{- define "knowledge-system.postgresServiceName" -}}
{{- include "knowledge-system.fullname" . }}-postgres
{{- end -}}

{{/*
Redis service name.
*/}}
{{- define "knowledge-system.redisServiceName" -}}
{{- include "knowledge-system.fullname" . }}-redis
{{- end -}}

{{/*
Frontend service name.
*/}}
{{- define "knowledge-system.frontendServiceName" -}}
{{- include "knowledge-system.fullname" . }}-frontend
{{- end -}}

{{/*
Backend service name.
*/}}
{{- define "knowledge-system.backendServiceName" -}}
{{- include "knowledge-system.fullname" . }}-backend
{{- end -}}

{{/*
PostgreSQL connection URL (dynamic, respects external config).
*/}}
{{- define "knowledge-system.databaseUrl" -}}
{{- if .Values.postgresql.external.enabled -}}
{{- printf "postgresql://%s@%s:%d/%s" .Values.postgresql.external.username .Values.postgresql.external.host (int .Values.postgresql.external.port) .Values.postgresql.external.database -}}
{{- else -}}
{{- printf "postgresql://%s:%s@%s:5432/%s" .Values.postgresql.auth.username .Values.postgresql.auth.password (include "knowledge-system.postgresServiceName" .) .Values.postgresql.auth.database -}}
{{- end -}}
{{- end -}}

{{/*
Redis connection URL (dynamic, respects external config and auth).
*/}}
{{- define "knowledge-system.redisUrl" -}}
{{- if .Values.redis.external.enabled -}}
{{- if .Values.redis.external.password -}}
{{- printf "redis://:%s@%s:%d/0" .Values.redis.external.password .Values.redis.external.host (int .Values.redis.external.port) -}}
{{- else -}}
{{- printf "redis://%s:%d/0" .Values.redis.external.host (int .Values.redis.external.port) -}}
{{- end -}}
{{- else -}}
{{- printf "redis://%s:6379/0" (include "knowledge-system.redisServiceName" .) -}}
{{- end -}}
{{- end -}}

{{/*
Redis host:port (used by Celery URLs).
*/}}
{{- define "knowledge-system.redisHost" -}}
{{- if .Values.redis.external.enabled -}}
{{- printf "%s:%d" .Values.redis.external.host (int .Values.redis.external.port) -}}
{{- else -}}
{{- printf "%s:6379" (include "knowledge-system.redisServiceName" .) -}}
{{- end -}}
{{- end -}}

{{/*
Celery broker URL (db=1) and result backend (db=2), respects external Redis.
*/}}
{{- define "knowledge-system.celeryBrokerUrl" -}}
{{- printf "redis://%s/1" (include "knowledge-system.redisHost" .) -}}
{{- end -}}

{{- define "knowledge-system.celeryResultBackend" -}}
{{- printf "redis://%s/2" (include "knowledge-system.redisHost" .) -}}
{{- end -}}

{{/*
Resource list block (requests + limits).
Usage: {{ include "knowledge-system.resources" .Values.backend.resources }}
*/}}
{{- define "knowledge-system.resources" -}}
{{- with . -}}
resources:
  {{- with .requests }}
  requests:
    {{- toYaml . | nindent 4 }}
  {{- end }}
  {{- with .limits }}
  limits:
    {{- toYaml . | nindent 4 }}
  {{- end }}
{{- end -}}
{{- end -}}

{{/*
Pod anti-affinity + topologySpreadConstraints block.
Usage: {{ include "knowledge-system.podAntiAffinity" (list . "backend") }}
$ = root context, component name = index . 1
*/}}
{{- define "knowledge-system.podAntiAffinity" -}}
{{- $root := index . 0 -}}
{{- $component := index . 1 -}}
{{- if $root.Values.podAntiAffinity.enabled }}
affinity:
  podAntiAffinity:
    {{- if eq $root.Values.podAntiAffinity.type "required" }}
    requiredDuringSchedulingIgnoredDuringExecution:
      - labelSelector:
          matchLabels:
            {{- include "knowledge-system.selectorLabels" $root | nindent 14 }}
            app.kubernetes.io/component: {{ $component }}
        topologyKey: {{ $root.Values.podAntiAffinity.topologyKey }}
    {{- else }}
    preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 100
        podAffinityTerm:
          labelSelector:
            matchLabels:
              {{- include "knowledge-system.selectorLabels" $root | nindent 14 }}
              app.kubernetes.io/component: {{ $component }}
          topologyKey: {{ $root.Values.podAntiAffinity.topologyKey }}
    {{- end }}
{{- end }}
{{- if $root.Values.topologySpreadConstraints.enabled }}
topologySpreadConstraints:
  - maxSkew: {{ $root.Values.topologySpreadConstraints.maxSkew }}
    topologyKey: {{ $root.Values.topologySpreadConstraints.topologyKey }}
    whenUnsatisfiable: {{ $root.Values.topologySpreadConstraints.whenUnsatisfiable }}
    labelSelector:
      matchLabels:
        {{- include "knowledge-system.selectorLabels" $root | nindent 8 }}
        app.kubernetes.io/component: {{ $component }}
{{- end }}
{{- end -}}
