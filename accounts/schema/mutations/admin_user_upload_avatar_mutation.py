import graphene
from graphene_file_upload.scalars import Upload
from graphql_jwt.decorators import login_required


class AdminUserUploadAvatarMutation(graphene.Mutation):
    class Arguments:
        image = Upload(
            required=False,
        )

    success = graphene.Boolean()
    avatar_url = graphene.String()

    @staticmethod
    @login_required
    def mutate(root, info, image):
        user = info.context.user
        user.avatar = image
        user.save()
        return {
            "success": True,
            "avatar_url": user.avatar.url,
        }
