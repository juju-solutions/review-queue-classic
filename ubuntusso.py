from velruse.api import register_provider
from velruse.providers.openid import OpenIDConsumer
from pyramid.security import NO_PERMISSION_REQUIRED


UBUNTU_SSO = 'ubuntu_sso'


class UbuntuSSOConsumer(OpenIDConsumer):
    def _update_authrequest(self, request, authrequest):
        super(UbuntuSSOConsumer, self)._update_authrequest(request,
                                                           authrequest)

    def _lookup_identifier(self, request, identifier):
        return 'http://login.ubuntu.com'


def add_ubuntu_login(config,
                     realm=None,
                     storage=None,
                     login_path='/login/openid',
                     callback_path='/login/openid/callback'):
    """
    Add an Ubuntu SSO login provider to the application.

    `storage` should be an object conforming to the
    `openid.store.interface.OpenIDStore` protocol. This will default
    to `openid.store.memstore.MemoryStore`.
    """
    provider = UbuntuSSOConsumer(UBUNTU_SSO, realm, storage)

    config.add_route(provider.login_route, login_path)
    config.add_view(provider, attr='login', route_name=provider.login_route,
                    permission=NO_PERMISSION_REQUIRED)

    config.add_route(provider.callback_route, callback_path,
                     use_global_views=True,
                     factory=provider.callback)

    register_provider(config, UBUNTU_SSO, provider)
