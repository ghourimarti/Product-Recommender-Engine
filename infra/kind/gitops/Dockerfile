# A git daemon for practising GitOps on kind (see git-server.yaml). alpine/git can't serve
# repositories: Alpine ships `git daemon` in a separate package, so this image adds it.
#   docker build -t p2-git-server:alpine3.22 infra/kind/gitops   (make kind-argocd does this)
FROM alpine:3.22
RUN apk add --no-cache git git-daemon
USER 65534:65534
ENTRYPOINT ["git"]
