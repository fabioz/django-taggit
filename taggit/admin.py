import re
from django.contrib import admin
from django.utils.translation import ugettext_lazy as _, ugettext

from begood_sites.admin import SiteModelAdmin

from taggit.models import Tag, TaggedItem


def tagged_items_count(obj):
    tagged_items_count = TaggedItem.objects.filter(tag=obj).count()
    return tagged_items_count
tagged_items_count.short_description = _('Tagged Items Count')


class TaggedItemInline(admin.StackedInline):
    model = TaggedItem


class TagAdmin(SiteModelAdmin):
    list_display = ["name", tagged_items_count,]
    list_filter = ["namespace",]
    search_fields = ["name",]
    prepopulated_fields = {'slug': ('name',)}
    list_per_page = 50

    actions = ['delete_selected']

    def delete_selected(modeladmin, request, queryset):
        sites = request.user.get_sites()
        for tag in queryset:
            tag.delete(sites)
    delete_selected.short_description = _("Delete selected Tags")

    def get_site_queryset(self, obj, user):
        return user.get_sites()

    def delete_model(self, request, obj):
        """
        Given a model instance delete it from the database.
        """
        sites = request.user.get_sites()
        obj.delete(sites)

    def save_form(self, request, form, change):
        """
        Given a model instance save it to the database.
        """
        obj = form.instance
        if obj.pk:
            original = Tag.objects.get(pk=obj.pk)
            if obj.name != original.name or obj.slug != original.slug:
                # The tag has been changed. If it's on multiple sites, keep the
                # original and create a new tag with the new name
                new_sites = form.cleaned_data['sites']
                obj_sites = obj.sites.all()
                if all(s in new_sites for s in obj_sites):
                    # This tag is not on any other sites, so allow this
                    # rename as usual
                    return form.save(commit=False)
                else:
                    # Create a new tag with the new name and slug
                    new_obj = Tag(name=obj.name, slug=obj.slug)
                    form.instance = new_obj
                    new_obj.save()

                    # Ugly, but this is the easiest way to make the redirect work
                    request.path = re.sub("/%d/" % obj.pk, "/%d/" % new_obj.pk, request.path)

                    # Switch the sites from the old to the new tag
                    for site in new_sites:
                        obj.sites.remove(site)
                        new_obj.sites.add(site)

                    # Re-tag all items belonging to the changed sites
                    tagged_items = obj.taggit_taggeditem_items.all()
                    for item in tagged_items:
                        if hasattr(item.content_object, 'sites'):
                            if item.content_object.sites.exclude(id__in=[s.id for s
                                in new_sites]).count() == 0:
                                item.delete()
                            if item.content_object.sites.filter(id__in=[s.id for s
                                in new_sites]).count() > 0:
                                item.content_object.tags.add(new_obj)

                    return new_obj
        return form.save(commit=False)

    def save_related(self, request, form, formsets, change):
        obj = form.instance
        original = obj.sites.all()
        user_sites = request.user.get_sites()
        new_sites = form.cleaned_data['sites']
        keep = [s for s in original if s not in user_sites]
        # When adding tags to new sites, keep any original sites.
        # Otherwise, keep any the user doesn't have access to
        obj.sites.clear()
        if change:
            for site in keep:
                obj.sites.add(site)
        else:
            for site in original:
                obj.sites.add(site)
        for site in new_sites:
            obj.sites.add(site)


admin.site.register(Tag, TagAdmin)
